from flask import Flask, jsonify
import logging
import sys

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def home_response():
    try:
        logger.info("GET / - Home page accessed")
        return jsonify({
            'message': '¡Hola Natalia! Estas aprendiendo kubernetes!',
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error in home endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'message': 'Internal server error',
            'status': 'error',
            'error': str(e)
        }), 500


def health_response():
    try:
        logger.info("GET /health - Health check")
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        logger.error(f"Error in health endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


def ready_response():
    try:
        logger.info("GET /ready - Readiness check")
        return jsonify({'status': 'ready'}), 200
    except Exception as e:
        logger.error(f"Error in ready endpoint: {str(e)}", exc_info=True)
        return jsonify({'status': 'not_ready', 'error': str(e)}), 503


@app.route('/', methods=['GET'])
def home():
    return home_response()


@app.route('/health', methods=['GET'])
def health():
    return health_response()


@app.route('/ready', methods=['GET'])
def ready():
    return ready_response()


@app.route('/api/', methods=['GET'])
def api_home():
    return home_response()


@app.route('/api/health', methods=['GET'])
def api_health():
    return health_response()


@app.route('/api/ready', methods=['GET'])
def api_ready():
    return ready_response()


@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {error}")
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}", exc_info=True)
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


if __name__ == '__main__':
    try:
        logger.info("Starting Flask server on port 5000...")
        logger.info("Available endpoints: /, /health, /ready, /api/, /api/health, /api/ready")
        app.run(host='0.0.0.0', port=5001, debug=False)
    except Exception as e:
        logger.error(f"Failed to start Flask server: {str(e)}", exc_info=True)
        sys.exit(1)
