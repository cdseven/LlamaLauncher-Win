E:\LlamaLauncher_Test\bin\llama-server.exe -m E:\LlamaLauncher_Test\models\Qwen3.6-35B-A3B-UD-Q6_K.gguf --jinja --ctx-size 4096 --batch-size 256 --ubatch-size 256 --flash-attn auto --chat-template-kwargs {\"enable_thinking\":false} -lv 4 --no-warmup --no-mmap 

rem #  -cmoe 
rem # Qwen3.6-27B-UD-Q5_K_XL.gguf	Qwen3.6-35B-A3B-UD-Q6_K.gguf
rem # --jinja --ctx-size 32768 --batch-size 256 --ubatch-size 256 --flash-attn auto --chat-template-kwargs {\"enable_thinking\":false}