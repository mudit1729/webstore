web: flask db upgrade && flask init-db && gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -
worker: rq worker ai-generation --with-scheduler --url $REDIS_URL
