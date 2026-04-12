#IMPORTING ALL NECESSARY LIBRARIES
from pickle import GET

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from datetime import datetime, timezone

app = Flask(__name__)

#AUTOMATICALLY HANDLING ACCESS-CONTROL-ALLOW-ORIGIN HEADER
CORS(app)

@app.route('/api/classify', methods=[GET])
def classify_name():
    #GETTING NAME FROM URL
    name = request.args.get('name')

    #ERROR HANDLING - in case of missing or empty name
    if not name or name.strip() == '':
        return jsonify({'status': 'error', 'message': 'Missing or empty name'}), 400


    #ERROR HANDLING - when name is not a string
    if name.isdigit():
        return jsonify({'status': 'error', 'message': 'Name should not be digits'}), 422



    #CALLING THE EXTERNAL API (Genderize API)
    try:
        url = f'https://api.genderize.io?name={name}'
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        raw_data = response.json()
    except requests.exceptions.RequestException:
        #HANDLING ERROR FROM UPSTREAM SERVER FAILURE
        return jsonify({'status': 'error', 'message': 'Upstream server failure'}), 502

    #HANDLING GENDERIZE EDGE CASES - NULL GENDER OR 0 COUNT
    if raw_data.get('gender') is None or raw_data.get('count', 0) == 0:
        return jsonify({'status': 'erro', 'message': 'The provided name has no available predictions'}), 400


    #EXTRACTION AND PROCESSING OF DATA
    gender = raw_data['gender']
    probability = raw_data['probability']
    sample_size = raw_data['count']

    #CONFIDENCE LOGIC
    is_confident = bool(probability >= 0.7 and sample_size >= 100)


    #GENERATING UTC ISO 8601 TIMESTAMP DYNAMICALLY
    processed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


    #RETURN THE SUCCESS RESPONSE
    return jsonify({
        'status': 'success',
        'data':{
            'name': name,
            'gender': gender,
            'probability': probability,
            'sample_size': sample_size,
            'is_confident': is_confident,
            'processed_at': processed_at
        }
    }), 200


#JUST TO RUN LOCALLY
if __name__ == '__main__':
    app.run(debug=True, port=5000)



