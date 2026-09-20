"""
Karaoke Builder - Main Application

Flask backend for the Karaoke Builder pipeline.
Provides REST API for:
- Project creation
- Pipeline execution
- Status monitoring
- Debug logs
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file

from .config import HOST, PORT, DEBUG, TEMP_DIR, FRONTEND_DIR, KEEP_TEMP_ON_SUCCESS
from .debug_logger import debug_logger
from .stage_runner import StageRunner
from .processors.base_processor import ProcessorContext
from .processors.demucs_processor import DemucsProcessor
from .processors.whisperx_processor import WhisperXProcessor
from .processors.pitch_processor import PitchProcessor
from .processors.packaging_processor import PackagingProcessor
from .models.validation import validate_project_inputs, check_system_readiness
from .utils.system_info import get_system_info, print_diagnostics


app = Flask(__name__, 
            static_folder=str(FRONTEND_DIR),
            static_url_path='')


# In-memory registry for active jobs
active_jobs = {}


# Serve frontend
@app.route('/')
def serve_index():
    """Serve main HTML page"""
    return send_from_directory(str(FRONTEND_DIR), 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS)"""
    return send_from_directory(str(FRONTEND_DIR), filename)


# API Routes
@app.route('/api/system/info', methods=['GET'])
def api_system_info():
    """Get system information"""
    info = get_system_info()
    return jsonify(info)


@app.route('/api/system/readiness', methods=['GET'])
def api_system_readiness():
    """Check system readiness for pipeline"""
    try:
        readiness = check_system_readiness()
        return jsonify(readiness)
    except Exception as e:
        # Return JSON error, not HTML
        return jsonify({
            "ready": False,
            "error": str(e),
            "components": {}
        }), 200  # Return 200 so frontend can parse JSON


@app.route('/api/validate', methods=['POST'])
def api_validate():
    """Validate project inputs"""
    try:
        # Get file paths from request
        data = request.json
        
        mp3_path = Path(data.get('mp3_path', ''))
        txt_path = Path(data.get('txt_path', ''))
        title = data.get('title', '')
        
        if not mp3_path.exists():
            return jsonify({
                "success": False,
                "error": f"MP3 file not found: {mp3_path}"
            }), 400
        
        if not txt_path.exists():
            return jsonify({
                "success": False,
                "error": f"TXT file not found: {txt_path}"
            }), 400
        
        success, details = validate_project_inputs(mp3_path, txt_path, title)
        
        return jsonify({
            "success": success,
            "details": details
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/pipeline/start', methods=['POST'])
def api_pipeline_start():
    """Start full pipeline"""
    try:
        # Handle file upload via multipart/form-data
        mp3_file = request.files.get('mp3')
        txt_file = request.files.get('txt')
        title = request.form.get('title', '')
        
        if not mp3_file or not txt_file:
            return jsonify({
                "success": False,
                "error": "MP3 and TXT files are required. Use multipart/form-data upload."
            }), 400
        
        # Create job directory FIRST
        job_id = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        job_dir = TEMP_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded files to job directory
        mp3_path = job_dir / "input.mp3"
        txt_path = job_dir / "lyrics.txt"
        
        mp3_file.save(str(mp3_path))
        txt_file.save(str(txt_path))
        
        # Verify files were saved correctly
        if not mp3_path.exists() or not mp3_path.is_file():
            return jsonify({
                "success": False,
                "error": f"Failed to save MP3 file. Path: {mp3_path}"
            }), 500
        
        if not txt_path.exists() or not txt_path.is_file():
            return jsonify({
                "success": False,
                "error": f"Failed to save TXT file. Path: {txt_path}"
            }), 500
        
        # Get absolute paths
        mp3_path = mp3_path.resolve()
        txt_path = txt_path.resolve()
        
        debug_logger.start_job(job_id)
        debug_logger.log_info("PIPELINE", f"Job started: {job_id}")
        debug_logger.log_info("PIPELINE", f"Job directory: {job_dir.resolve()}")
        debug_logger.log_info("PIPELINE", f"Uploaded MP3 saved: {mp3_path}")
        debug_logger.log_info("PIPELINE", f"Uploaded TXT saved: {txt_path}")
        
        # Use title from form or generate from filename
        if not title or not title.strip():
            title = mp3_path.stem
        
        debug_logger.log_info("PIPELINE", f"Starting pipeline for: {title}")
        debug_logger.log_info("PIPELINE", f"MP3: {mp3_path}")
        debug_logger.log_info("PIPELINE", f"TXT: {txt_path}")
        
        # Initialize context with SAVED file paths
        context = ProcessorContext(
            job_id=job_id,
            work_dir=job_dir,
            input_file=mp3_path,
            lyrics_file=txt_path,
            title=title
        )
        
        # Store job info in app config (for retry functionality)
        active_jobs[job_id] = {
            'id': job_id,
            'dir': str(job_dir),
            'context': context
        }
        app.config['current_job'] = active_jobs[job_id]
        
        # Run pipeline stages sequentially
        results = {}
        
        # Stage 1: Demucs
        debug_logger.log_info("PIPELINE", "Starting Stage 1: Demucs")
        demucs = DemucsProcessor(context)
        results['demucs'] = demucs.execute().to_dict()
        
        if not results['demucs']['success']:
            debug_logger.log_error("PIPELINE", f"Demucs failed: {results['demucs'].get('stderr', 'Unknown error')}")
            return _pipeline_failed(results, job_dir, 'demucs')
        
        debug_logger.log_info("PIPELINE", "Demucs completed successfully")
        
        # Stage 2: WhisperX
        debug_logger.log_info("PIPELINE", "Starting Stage 2: WhisperX")
        whisperx = WhisperXProcessor(context)
        results['whisperx'] = whisperx.execute().to_dict()
        
        if not results['whisperx']['success']:
            debug_logger.log_error("PIPELINE", f"WhisperX failed: {results['whisperx'].get('stderr', 'Unknown error')}")
            return _pipeline_failed(results, job_dir, 'whisperx')
        
        debug_logger.log_info("PIPELINE", "WhisperX completed successfully")
        
        # Stage 3: Pitch
        debug_logger.log_info("PIPELINE", "Starting Stage 3: Pitch")
        pitch = PitchProcessor(context)
        results['pitch'] = pitch.execute().to_dict()
        
        if not results['pitch']['success']:
            debug_logger.log_error("PIPELINE", f"Pitch failed: {results['pitch'].get('stderr', 'Unknown error')}")
            return _pipeline_failed(results, job_dir, 'pitch')
        
        debug_logger.log_info("PIPELINE", "Pitch completed successfully")
        
        # Stage 4: Packaging
        debug_logger.log_info("PIPELINE", "Starting Stage 4: Packaging")
        packaging = PackagingProcessor(context)
        results['packaging'] = packaging.execute().to_dict()
        
        if not results['packaging']['success']:
            debug_logger.log_error("PIPELINE", f"Packaging failed: {results['packaging'].get('stderr', 'Unknown error')}")
            return _pipeline_failed(results, job_dir, 'packaging')
        
        debug_logger.log_info("PIPELINE", "Packaging completed successfully")
        
        # Success!
        debug_logger.end_job(True)
        
        response = {
            "success": True,
            "job_id": job_id,
            "results": results,
            "output": {
                "karaoke_json": str(context.karaoke_json),
                "minus_mp3": str(context.minus_mp3)
            }
        }
        
        # Optionally clean up temp files
        if KEEP_TEMP_ON_SUCCESS:
            pass  # Keep for now
        else:
            # Don't delete yet - needed for preview
            pass
        
        return jsonify(response)
        
    except Exception as e:
        debug_logger.log_error("PIPELINE", f"Pipeline failed: {str(e)}")
        import traceback
        debug_logger.log_error("PIPELINE", traceback.format_exc())
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def _pipeline_failed(results, job_dir, failed_stage):
    """Handle pipeline failure with detailed stage information"""
    debug_logger.end_job(False)
    
    # Find the failed stage result
    failed_result = results.get(failed_stage, {})
    
    # Build detailed error response
    error_response = {
        "success": False,
        "job_id": job_dir.name,
        "stage": failed_stage,  # Specific stage that failed
        "error": f"Pipeline failed at stage: {failed_stage}",
        "temp_dir": str(job_dir),
        "results": results
    }
    
    # Add detailed error info from the failed stage
    if failed_result:
        error_response["exit_code"] = failed_result.get('exit_code')
        error_response["stderr"] = failed_result.get('stderr', '')
        error_response["stdout"] = failed_result.get('stdout', '')
        error_response["error_message"] = failed_result.get('error_message', '')
        error_response["duration"] = failed_result.get('duration', 0)
        error_response["outputs"] = failed_result.get('outputs', [])
    
    return jsonify(error_response), 400


@app.route('/api/pipeline/stage/<stage_name>', methods=['POST'])
def api_run_stage(stage_name):
    """Run individual pipeline stage (for development/testing)"""
    # Implementation for running individual stages
    # Similar to full pipeline but runs only specified stage
    
    stages = {
        'demucs': DemucsProcessor,
        'whisperx': WhisperXProcessor,
        'pitch': PitchProcessor,
        'packaging': PackagingProcessor
    }
    
    if stage_name not in stages:
        return jsonify({
            "success": False,
            "error": f"Unknown stage: {stage_name}"
        }), 400
    
    # Get job context from current job
    job_info = app.config.get('current_job')
    if not job_info:
        return jsonify({
            "success": False,
            "error": "No active job. Run full pipeline first."
        }), 400
    
    context = job_info['context']
    processor = stages[stage_name](context)
    result = processor.execute()
    
    return jsonify(result.to_dict())


@app.route('/api/logs', methods=['GET'])
def api_get_logs():
    """Get debug logs"""
    stage = request.args.get('stage')
    logs = debug_logger.get_logs(stage)
    return jsonify(logs)


@app.route('/api/logs/report', methods=['GET'])
def api_get_debug_report():
    """Get full debug report"""
    report = debug_logger.get_debug_report()
    return app.response_class(
        response=report,
        status=200,
        mimetype='text/plain'
    )


@app.route('/api/logs/save', methods=['POST'])
def api_save_log():
    """Save debug log to file"""
    filepath = debug_logger.save_debug_log()
    return jsonify({
        "success": True,
        "filepath": filepath
    })


@app.route('/api/output/karaoke.json', methods=['GET'])
def api_get_karaoke_json():
    """Get generated karaoke JSON"""
    job_info = app.config.get('current_job')
    if not job_info:
        return jsonify({"error": "No active job"}), 404
    
    context = job_info['context']
    if not context.karaoke_json or not context.karaoke_json.exists():
        return jsonify({"error": "Karaoke JSON not found"}), 404
    
    return send_file(
        str(context.karaoke_json),
        mimetype='application/json',
        as_attachment=True,
        download_name='karaoke.json'
    )


@app.route('/api/output/minus.mp3', methods=['GET'])
def api_get_minus_mp3():
    """Get generated minus MP3"""
    job_info = app.config.get('current_job')
    if not job_info:
        return jsonify({"error": "No active job"}), 404
    
    context = job_info['context']
    if not context.minus_mp3 or not context.minus_mp3.exists():
        return jsonify({"error": "Minus MP3 not found"}), 404
    
    return send_file(
        str(context.minus_mp3),
        mimetype='audio/mpeg',
        as_attachment=False
    )


if __name__ == '__main__':
    print("=" * 60)
    print("Karaoke Builder — Starting Server")
    print("=" * 60)
    print()
    
    # Print system diagnostics
    print_diagnostics()
    print()
    
    # Start server
    print(f"Starting Flask server on http://{HOST}:{PORT}")
    print(f"Frontend: {FRONTEND_DIR}")
    print()
    
    app.run(host=HOST, port=PORT, debug=DEBUG)
