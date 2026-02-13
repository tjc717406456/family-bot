import traceback

try:
    from db.database import init_db
    from web import create_app

    if __name__ == "__main__":
        init_db()
        app = create_app()
        print("启动 Web 服务: http://localhost:5000")
        app.run(host="0.0.0.0", port=5000, debug=True)
except Exception as e:
    traceback.print_exc()
