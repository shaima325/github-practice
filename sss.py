from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.nexus_token import get_cached_nexus_token
import requests
from app.utils.api_logger import log_api_call
import app.utils.common_functions as user_function
from app.models.activations import Activation
from app.extensions import db

socs_bp = Blueprint('socs', __name__)

@socs_bp.route("/add-wfc", methods=["POST"])
@jwt_required()
def add_wfc():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    mdn = data.get("mdn")
    iccid = data.get("iccid")
    address = data.get("address", {})
    address1 = address.get("address1")
    address2 = address.get("address2", "")
    city = address.get("city")
    state = address.get("state")
    zip_code = address.get("zip")

    if not mdn or not iccid or not address1 or not city or not state or not zip_code:
        return jsonify({"error": "MDN, ICCID, and complete address are required"}), 400

    # Get Nexus token
    jwt_token, status_code = get_cached_nexus_token()
        
    if status_code != 200:
        return jsonify({"error": "Internal Server Error"}), 501

    if not jwt_token:
        return jsonify({"error": "Internal Server Error"}), 501

    # Call Add WFC API
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "partnerTransactionId": "",
        "msisdn": mdn,
        "iccid": iccid,
        "socs": [
            {
                "soc": "WFC"
            }
        ],
        "e911Address": {
            "street1": address1,
            "street2": address2,
            "city": city,
            "state": state,
            "zip": zip_code
        }
    }

    nexus_response = requests.put(current_app.config['NEXUS_ADD_WFC_URL'], json=payload, headers=headers)

    # Log API call
    try:
        log_api_call(current_app.config['NEXUS_ADD_WFC_URL'], payload, nexus_response.text, nexus_response.status_code)
    except Exception:
        pass

    if nexus_response.status_code != 200:
        return jsonify({"error": "Failed to add WFC"}), 500

    result_json = nexus_response.json()
    data_array = result_json.get("result", {}).get("data", [])

    # Add customer note
    activation = Activation.query.filter_by(iccid=iccid, msisdn=mdn, activation_status='active').first()
    if activation:
        user_function.add_customer_note(
            customer_id=activation.customer_id,
            note="Add WFC SOC successful via Add WFC API",
            note_type="WFC Added",
            created_by=user_id,
            iccid=iccid
        )
        db.session.commit()

    return jsonify({
        "success": True,
        "data": data_array
    }), 200
