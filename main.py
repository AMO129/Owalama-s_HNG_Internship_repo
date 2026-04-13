from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone
import os

app = Flask(__name__)
CORS(app)

@app.route('/api/classify', methods=['GET'])
def classify_name():
    #GETTING NAME FROM URL
    name = request.args.get('name')

    
   
    #ERROR HANDLING - Missing or empty name
    if not name or name.strip() == '':
        return jsonify({'status': 'error', 
                        'message': 'Please provide a name'}), 400

    #ERROR HANDLING - When name is just digits
    if name.isdigit():
        return jsonify({'status': 'error', 
                        'message': 'Name should not be digits'}), 422

    #CALLING THE EXTERNAL API (Genderize API)
    try:
        url = f'https://api.genderize.io?name={name}'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        raw_data = response.json()
    except requests.exceptions.RequestException as e:
        
        #IN CASE THE INTERNET IS DOWN
        print(f"Log: Connection Error -> {e}")

        return jsonify({'status': 'error', 
                        'message': 'Upstream server failure'}), 502

    #HANDLING CASES WHERE GENDERIZE DOES NOT RECOGNIZE THE NAME
    gender = raw_data.get('gender')
    if not gender:
        return jsonify({
            'status': 'error', 
            'message': 'The provided name has no available predictions'}), 404

    #EXTRACTION AND PROCESSING
   
    probability = raw_data.get('probability', 0)
    sample_size = raw_data.get('count', 0)

    #CONFIDENCE LOGIC
    is_confident = bool(probability >= 0.7 and sample_size >= 100)

    #GENERATING TIMESTAMP
    processed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    #FINAL SUCCESS RESPONSE (Moved to the bottom)
    return jsonify({
        'status': 'success',
        'data': {
            'name': name.capitalize(),
            'gender': gender,
            'probability': probability,
            'sample_size': sample_size,
            'is_confident': bool(is_confident),
            'processed_at': processed_at
        }
    }), 200

#Railway-Compatibility
if __name__ == '__main__':

    #Railway provides a port via environment variables
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
