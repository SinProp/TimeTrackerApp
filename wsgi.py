from server import app, start_scheduler_if_enabled

application = app
start_scheduler_if_enabled()

if __name__ == "__main__":
    application.run()
