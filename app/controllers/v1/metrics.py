"""
HTTP Controllers for H21 API - Core Portal Metrics endpoints.
"""
from flask import Blueprint, request, jsonify
from ..utils.auth import require_auth
from ..services.MetricsService import MetricsService

metrics_bp = Blueprint('metrics', __name__, url_prefix='/api/v1')


def create_metrics_controller(metrics_service: MetricsService):
    """
    Factory function to create metrics controller with injected service.
    """
    
    @metrics_bp.route('/metrics/users/total', methods=['GET'])
    @require_auth
    def get_total_users():
        """
        H21.1: GET /api/v1/metrics/users/total
        Returns total number of registered customers.
        """
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            # Note: Date filtering is not implemented in this version
            # as metrics are maintained in-memory without date indexing
            total = metrics_service.get_total_customers()
            
            response = {
                "status": "success",
                "total_customers": total
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"[H21.1] Error: {e}")
            return jsonify({
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }), 500
    
    @metrics_bp.route('/core/metrics/conversations/summary', methods=['GET'])
    @require_auth
    def get_conversations_summary():
        """
        H21.2: GET /api/v1/core/metrics/conversations/summary
        Returns conversation statistics.
        """
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            summary = metrics_service.get_conversation_summary()
            
            response = {
                "status": "success",
                **summary
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"[H21.2] Error: {e}")
            return jsonify({
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }), 500
    
    @metrics_bp.route('/core/metrics/consultations/satisfaction', methods=['GET'])
    @require_auth
    def get_satisfaction():
        """
        H21.3: GET /api/v1/core/metrics/consultations/satisfaction
        Returns customer satisfaction distribution.
        """
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            satisfaction = metrics_service.get_satisfaction_metrics()
            
            response = {
                "status": "success",
                **satisfaction
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"[H21.3] Error: {e}")
            return jsonify({
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }), 500
    
    @metrics_bp.route('/core/metrics/consultations/offload-rate', methods=['GET'])
    @require_auth
    def get_offload_rate():
        """
        H21.4: GET /api/v1/core/metrics/consultations/offload-rate
        Returns overall offload rate.
        """
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            offload_rate = metrics_service.get_offload_rate()
            
            response = {
                "status": "success",
                **offload_rate
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"[H21.4] Error: {e}")
            return jsonify({
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }), 500
    
    @metrics_bp.route('/core/metrics/consultations/offload-rate-by-partner', methods=['GET'])
    @require_auth
    def get_offload_rate_by_partner():
        """
        H21.5: GET /api/v1/core/metrics/consultations/offload-rate-by-partner
        Returns per-partner offload rate.
        """
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            partner_id = request.args.get('partner_id')
            
            offload_data = metrics_service.get_partner_offload_rate(partner_id)
            
            response = {
                "status": "success",
                **offload_data
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return jsonify(response), 200
            
        except Exception as e:
            print(f"[H21.5] Error: {e}")
            return jsonify({
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred while retrieving metrics"
            }), 500
    
    return metrics_bp
