web: FLASK_ENV=production flask db upgrade && flask init-db && flask seed-demo && gunicorn "app:create_app('production')" --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile -
worker: FLASK_ENV=production rq worker ai-generation --with-scheduler --url $REDIS_URL
