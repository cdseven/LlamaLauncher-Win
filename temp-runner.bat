@echo off
echo Starting Q38-27B-HauHau-Q5_K_P.gguf (32768 token context):
taskkill /F /IM llama-server.exe 2>nul
timeout /t 1 /nobreak >nul
E:\LlamaLauncher_Test\bin\llama-server.exe -m E:\LlamaLauncher_Test\models\Q38-27B-HauHau-Q5_K_P.gguf --jinja --ctx-size 32768 --batch-size 256 --ubatch-size 256 --flash-attn auto --chat-template-kwargs {\"enable_thinking\":false}
pause