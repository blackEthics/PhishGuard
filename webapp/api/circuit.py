"""api/circuit.py — Blueprint for the quantum circuit visualizer endpoint."""

from flask import Blueprint, jsonify, request

import models.loader as loader

circuit_bp = Blueprint("circuit", __name__)

_MAX_URL_LENGTH = 2048


@circuit_bp.route("/api/circuit")
def api_circuit():
    """Return the 4 quantum angle parameters for a URL.

    Query param: url (str, required, max 2048 chars)
    Returns: angles array, n_qubits, n_layers, pipeline description.
    """
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    if len(url) > _MAX_URL_LENGTH:
        return jsonify({"error": f"URL too long (max {_MAX_URL_LENGTH} characters)"}), 400

    if not loader._initialized:
        return jsonify({"error": "Models not yet loaded — try again in a moment"}), 503

    try:
        angles = loader.get_angles_for_url(url)
    except Exception as exc:
        return jsonify({"error": f"Could not compute angles: {exc}"}), 500

    return jsonify({
        "url":      url,
        "n_qubits": 4,
        "n_layers": 3,
        "angles":   [round(float(a), 4) for a in angles],
        "pipeline": "TF-IDF(50k) → SVD-50 → +6 URL features → StandardScaler → PCA-4 → MinMaxScaler[0,π]",
    })
