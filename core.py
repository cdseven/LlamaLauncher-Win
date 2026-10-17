import subprocess
import os
import sys
import re
import configparser

def app_dir():
    """Get the directory where the executable/script lives (for writable files)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

_BASE_DIR = app_dir()
_INI_PATH = os.path.join(_BASE_DIR, 'ini.ini')

def _resolve(path):
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(_BASE_DIR, path))

def _load_config():
    config = configparser.ConfigParser()
    if os.path.exists(_INI_PATH):
        config.read(_INI_PATH)
    models = config.get('paths', 'models', fallback='./models')
    bin_ = config.get('paths', 'bin', fallback='./bin')
    models_resolved = _resolve(models)
    bin_resolved = _resolve(bin_)
    if not os.path.isdir(models_resolved):
        models_resolved = _resolve('./models')
    if not os.path.isdir(bin_resolved):
        bin_resolved = _resolve('./bin')
    return models_resolved, bin_resolved

MODELS_DIR, BIN_DIR = _load_config()
RUNNER_BAT = os.path.join(_BASE_DIR, 'temp-runner.bat')

class Core:
    def __init__(self):
        self.stop_on_exit = True
        self.window = None
        self._help_window = None

    def get_models(self):
        try:
            files = [f for f in os.listdir(MODELS_DIR) if f.endswith('.gguf')]
            files.sort()
            result = []
            for f in files:
                size_bytes = os.path.getsize(os.path.join(MODELS_DIR, f))
                size_g = size_bytes / (1024 ** 3)
                if size_g >= 100:
                    size_str = f'[{size_g / 1024:.1f}T]'
                else:
                    size_str = f'[{size_g:.1f}G]'
                match = re.search(r'(\d+\.?\d*)B', f, re.IGNORECASE)
                if match:
                    params = float(match.group(1))
                    if params >= 1:
                        param_str = f'[{int(params):03d}B]'
                    else:
                        param_str = f'[{params:.1f}B]'
                else:
                    param_str = '[000B]'
                result.append({'file': f, 'label': f'{param_str} - {f} - {size_str}'})
            return result
        except Exception:
            return []

    def get_paths(self):
        return {'models': MODELS_DIR, 'bin': BIN_DIR}

    def get_extras(self):
        try:
            path = resource_path(os.path.join('assets', 'extras.json'))
            with open(path, 'r', encoding='utf-8') as f:
                import json
                return json.load(f)
        except Exception:
            return {}


    def _save_config(self, key, value):
        config = configparser.ConfigParser()
        config.read(_INI_PATH)
        if not config.has_section('paths'):
            config.add_section('paths')
        config.set('paths', key, value)
        with open(_INI_PATH, 'w') as f:
            config.write(f)

    def reset_models_dir(self):
        global MODELS_DIR
        self._save_config('models', './models')
        MODELS_DIR = _resolve('./models')
        return MODELS_DIR

    def reset_bin_dir(self):
        global BIN_DIR
        self._save_config('bin', './bin')
        BIN_DIR = _resolve('./bin')
        return BIN_DIR

    def set_models_dir(self, path):
        global MODELS_DIR
        MODELS_DIR = path
        self._save_config('models', path)

    def set_bin_dir(self, path):
        global BIN_DIR
        BIN_DIR = path
        self._save_config('bin', path)

    def open_help(self, section):
        import webview
        help_file = resource_path(os.path.join('assets', 'help.html'))
        url = f'file:///{help_file.replace(os.sep, "/")}#{section}'

        if self._help_window is not None:
            try:
                self._help_window.load_url(url)
                self._help_window.on_top = True
                self._help_window.on_top = False
                return
            except Exception:
                self._help_window = None

        self._help_window = webview.create_window(
            title='Help',
            url=url,
            width=600,
            height=500,
            resizable=True,
        )

        def on_help_closed():
            self._help_window = None

        self._help_window.events.closing += on_help_closed

    def set_stop_on_exit(self, value):
        self.stop_on_exit = value

    def browse_models(self):
        import webview
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            path = result[0]
            self.set_models_dir(path)
            return path
        return None

    def browse_bin(self):
        import webview
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            path = result[0]
            self.set_bin_dir(path)
            return path
        return None

    def launch(self, model, ctx_size, disable_cot_template, disable_cot_override, backend='server', custom_args=''):
        self.save_pref('last_model', model)

        model_path = os.path.join(MODELS_DIR, model)
        exe_name = 'llama-cli.exe' if backend == 'cli' else 'llama-server.exe'
        exe_path = os.path.join(BIN_DIR, exe_name)
        ctx_tokens = str(ctx_size)

        cot_flags = []
        if disable_cot_template:
            cot_flags.append('--chat-template-kwargs {\\"enable_thinking\\":false}')
        if disable_cot_override:
            cot_flags.append('--reasoning-budget 0 --reasoning-format none')
        cot_flags_str = ' '.join(cot_flags)

        extra = f'{cot_flags_str} {custom_args}'.strip()

        if backend == 'cli':
            bat_lines = [
                '@echo off',
                f'echo Starting {model} ({ctx_size} token context) via llama-cli:',
                f'{exe_path} -m {model_path} --jinja --ctx-size {ctx_tokens} --flash-attn auto {extra}'.strip(),
                'pause',
            ]
        else:
            bat_lines = [
                '@echo off',
                f'echo Starting {model} ({ctx_size} token context):',
                'taskkill /F /IM llama-server.exe 2>nul',
                'timeout /t 1 /nobreak >nul',
                f'{exe_path} -m {model_path} --jinja --ctx-size {ctx_tokens} --batch-size 256 --ubatch-size 256 --flash-attn auto {extra}'.strip(),
                'pause',
            ]

        if os.path.exists(RUNNER_BAT):
            os.remove(RUNNER_BAT)
        with open(RUNNER_BAT, 'w') as f:
            f.write('\n'.join(bat_lines))
        subprocess.Popen(f'start cmd /c {RUNNER_BAT}', shell=True)

    def validate_paths(self):
        models_exists = os.path.isdir(MODELS_DIR)
        bin_exists = os.path.isdir(BIN_DIR)
        gguf_files = []
        if models_exists:
            gguf_files = [f for f in os.listdir(MODELS_DIR) if f.endswith('.gguf')]
        has_server = bin_exists and os.path.isfile(os.path.join(BIN_DIR, 'llama-server.exe'))
        return {
            'models_exists': models_exists,
            'models_has_files': len(gguf_files) > 0,
            'model_count': len(gguf_files),
            'bin_exists': bin_exists,
            'has_server': has_server,
        }
    
    def download_model(self):
        import webview
        picker_file = resource_path(os.path.join('assets', 'download_picker.html'))
        url = f'file:///{picker_file.replace(os.sep, "/")}'

        if hasattr(self, '_download_window') and self._download_window is not None:
            try:
                self._download_window.on_top = True
                self._download_window.on_top = False
                return
            except Exception:
                self._download_window = None

        self._download_window = webview.create_window(
            title='Download Model',
            url=url,
            width=750,
            height=280,
            resizable=False,
            js_api=self,
        )

        def on_picker_closed():
            self._download_window = None

        self._download_window.events.closing += on_picker_closed

    def start_download(self, url, filename):
        dest = os.path.join(MODELS_DIR, filename)
        os.makedirs(MODELS_DIR, exist_ok=True)
        bat_lines = [
            '@echo off',
            f'echo Downloading {filename}...',
            f'echo Destination: {dest}',
            f'curl -L --progress-bar -o "{dest}" "{url}"',
            'echo.',
            'echo Download complete.',
            'pause',
        ]
        bat_path = os.path.join(_BASE_DIR, 'temp-downloader.bat')
        if os.path.exists(bat_path):
            os.remove(bat_path)
        with open(bat_path, 'w') as f:
            f.write('\n'.join(bat_lines))
        subprocess.Popen(f'start cmd /c "{bat_path}"', shell=True)
        if self._download_window is not None:
            try:
                self._download_window.destroy()
                self._download_window = None
            except Exception:
                pass


    def download_bin(self):
        import webview
        picker_file = resource_path(os.path.join('assets', 'bin_picker.html'))
        url = f'file:///{picker_file.replace(os.sep, "/")}'

        if hasattr(self, '_bin_window') and self._bin_window is not None:
            try:
                self._bin_window.on_top = True
                self._bin_window.on_top = False
                return
            except Exception:
                self._bin_window = None

        self._bin_window = webview.create_window(
            title='Download Bin',
            url=url,
            width=560,
            height=320,
            resizable=True,
            js_api=self,
        )

        def on_bin_closed():
            self._bin_window = None

        self._bin_window.events.closing += on_bin_closed

    def start_download_bin(self, url, filename):
        dest_zip = os.path.join(BIN_DIR, filename)
        os.makedirs(BIN_DIR, exist_ok=True)
        bat_lines = [
            '@echo off',
            f'echo Downloading {filename}...',
            f'curl -L --progress-bar -o "{dest_zip}" "{url}"',
            'echo.',
            f'echo Extracting {filename}...',
            f'powershell -Command "Expand-Archive -Path \'{dest_zip}\' -DestinationPath \'{BIN_DIR}\' -Force"',
            f'del "{dest_zip}"',
            'echo.',
            'echo Done.',
            'pause',
        ]
        bat_path = os.path.join(_BASE_DIR, 'temp-bin-downloader.bat')
        if os.path.exists(bat_path):
            os.remove(bat_path)
        with open(bat_path, 'w') as f:
            f.write('\n'.join(bat_lines))
        subprocess.Popen(f'start cmd /c "{bat_path}"', shell=True)
        if self._bin_window is not None:
            try:
                self._bin_window.destroy()
                self._bin_window = None
            except Exception:
                pass




    # --- Preference persistence pattern ---
    # To save/restore a new UI preference:
    # 1. Add get_last_X() and save_last_X() methods here (read/write ini.ini [preferences])
    # 2. In index.html, call save_last_X() when the value changes (e.g. onchange)
    # 3. In index.html pywebviewready, call get_last_X() and restore the UI element
    # See get_last_ctx / save_last_ctx for reference implementation.


    def get_pref(self, key, default=None):
        try:
            config = configparser.ConfigParser()
            if os.path.exists(_INI_PATH):
                config.read(_INI_PATH)
                if config.has_section('preferences'):
                    return config.get('preferences', key, fallback=default)
            return default
        except Exception:
            return default

    def save_pref(self, key, value):
        try:
            config = configparser.ConfigParser()
            if os.path.exists(_INI_PATH):
                config.read(_INI_PATH)
            if not config.has_section('preferences'):
                config.add_section('preferences')
            config.set('preferences', key, str(value))
            with open(_INI_PATH, 'w') as f:
                config.write(f)
        except Exception:
            pass


    # END SAVE / RESTORE PREVIOUS UI PREFERENCE PERSISTENCE PATTERN COMMENTS


    def set_startup_data(self, data):
        self._startup_data = data
        self._system_info_cache = data.get('system')


    def get_startup_data(self):
        return self._startup_data


    def get_system_info(self):
        # return {'vram': '-', 'ram': '-'}  # stub
        return self._system_info_cache or {'vram': '-', 'ram': '-'}
