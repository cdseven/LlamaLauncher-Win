import webview
import os
import sys
import subprocess
from core import Core




def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

HTML_FILE = resource_path('index.html')

def make_on_closing(api):
    def on_closing():
        if api.stop_on_exit:
            subprocess.run('taskkill /F /IM llama-server.exe 2>nul', shell=True)
        if api._help_window is not None:
            try:
                api._help_window.destroy()
            except Exception:
                pass
    return on_closing

def main():
    api = Core()

    def safe(label, fn, default):
        try:
            return fn()
        except Exception:
            return default

    
    from assets.memory_detect import detect_memory

    info = safe('detect_memory', detect_memory, {'ram': {}, 'gpus': []})
    ram = info.get('ram') or {}
    gpus = info.get('gpus') or []
    vram_gb = gpus[0].get('vram_gb') if gpus else None
    ram_gb = ram.get('gb')
    
    system = {
        'vram': f'{vram_gb:.1f} GB' if vram_gb is not None else '-',
        'ram': f'{ram_gb:.1f} GB' if ram_gb is not None else '-',
    } 

    startup_data = {
        'paths':      safe('paths',      api.get_paths,       {'models': '', 'bin': ''}),
        'models':     safe('models',     api.get_models,      []),
        'extras':     safe('extras',     api.get_extras,      {}),
        'validation': safe('validation', api.validate_paths,  {
            'models_exists': False, 'models_has_files': False,
            'model_count': 0, 'bin_exists': False, 'has_server': False,
        }),
        'prefs': {
            'last_model':   safe('last_model',   lambda: api.get_pref('last_model'),                       None),
            'last_ctx':     safe('last_ctx',     lambda: api.get_pref('last_ctx'),                         None),
            'cot_template': safe('cot_template', lambda: api.get_pref('cot_template', 'true') == 'true',   True),
        },
        'system': system,
    }

    api.set_startup_data(startup_data)


    window = webview.create_window(
        title='Llama Launcher',
        url=HTML_FILE,
        width=900,
        height=800,
        resizable=True,
        js_api=api,
    )
    api.window = window
    window.events.closing += make_on_closing(api)

    # Retry navigation to index.html on startup to fix silent WebView2 hangs.
    # Double-load on success is harmless; COM warnings are benign.
    def on_webview_started():
        html_url = f'file:///{HTML_FILE.replace(os.sep, "/")}'
        window.load_url(html_url)

    webview.start(on_webview_started, debug=False, icon="assets/veritech-1.ico")


if __name__ == '__main__':
    main()