from flask import Flask, render_template, jsonify
import pytest
import sys
import io

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/run_tests')
def run_tests():
    # Redirect stdout to capture pytest output
    captured_output = io.StringIO()
    sys.stdout = captured_output

    # Run pytest
    pytest.main(['-v', 'test_api.py'])

    # Restore stdout
    sys.stdout = sys.__stdout__

    # Get the captured output
    test_output = captured_output.getvalue()

    # Parse the output to get results
    lines = test_output.split('\n')
    results = []
    for line in lines:
        if line.startswith('test_'):
            parts = line.split()
            results.append({
                'name': parts[0],
                'result': 'PASSED' if 'PASSED' in line else 'FAILED'
            })

    return jsonify({
        'output': test_output,
        'results': results
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)