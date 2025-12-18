"""
HTTP Controllers for H21 API - Core Portal Metrics endpoints.
"""
from flask import request
from flask_restx import Namespace, Resource
from ...utils.auth import require_auth
from ...services.MetricsService import MetricsService

api = Namespace('metrics', description='Metrics operations')

# Initialize metrics service
metrics_service = MetricsService()


@api.route('/users/total')
class TotalUsers(Resource):
    @api.doc('get_total_users')
    @require_auth
    def get(self):
        """H21.1: Returns total number of registered customers"""
        try:
            from_date = request.args.get('from_date')
            to_date = request.args.get('to_date')
            
            total = metrics_service.get_total_customers()
            
            response = {
                "status": "success",
                "total_customers": total
            }
            
            if from_date:
                response["from_date"] = from_date
            if to_date:
                response["to_date"] = to_date
            
            return response, 200
            
        except Exception as e:
            print(f"[H21.1] Error: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }, 500


@api.route('/conversations/summary')
class ConversationsSummary(Resource):
    @api.doc('get_conversations_summary')
    @require_auth
    def get(self):
        """H21.2: Returns conversation statistics"""
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
            
            return response, 200
            
        except Exception as e:
            print(f"[H21.2] Error: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }, 500


@api.route('/consultations/satisfaction')
class Satisfaction(Resource):
    @api.doc('get_satisfaction')
    @require_auth
    def get(self):
        """H21.3: Returns customer satisfaction distribution"""
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
            
            return response, 200
            
        except Exception as e:
            print(f"[H21.3] Error: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }, 500


@api.route('/consultations/offload-rate')
class OffloadRate(Resource):
    @api.doc('get_offload_rate')
    @require_auth
    def get(self):
        """H21.4: Returns overall offload rate"""
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
            
            return response, 200
            
        except Exception as e:
            print(f"[H21.4] Error: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }, 500


@api.route('/consultations/offload-rate-by-partner')
class OffloadRateByPartner(Resource):
    @api.doc('get_offload_rate_by_partner')
    @require_auth
    def get(self):
        """H21.5: Returns per-partner offload rate"""
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
            
            return response, 200
            
        except Exception as e:
            print(f"[H21.5] Error: {e}")
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            }, 500
