import os
import logging
from MyFlaskApp.__init__ import create_app

# Show Werkzeug request logs even when debug=False
logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.INFO)

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
    app.run(debug=debug, host='0.0.0.0')