@echo off
call .venv\Scripts\activate

start cmd /k "uvicorn Logic.fastapi_app:app"

cd full_factory_management_system_ui
start cmd /k "npm run dev"

timeout /t 3

start http://localhost:3000