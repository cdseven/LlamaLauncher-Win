let tooltips = {};
let clickArgs = '';

const CTX_NORMAL = [
    { value: 16384, label: '16K' },
    { value: 32768, label: '32K' },
    { value: 65536, label: '64K' },
];
const CTX_EXTENDED = [
    { value: 4096, label: '4K' },
    { value: 8192, label: '8K' },
    { value: 16384, label: '16K' },
    { value: 32768, label: '32K' },
    { value: 49152, label: '48K' },
    { value: 65536, label: '64K' },
    { value: 131072, label: '128K' },
    { value: 196608, label: '192K' },
    { value: 204800, label: '200K' },
    { value: 262144, label: '256K' },
    { value: 524288, label: '512K' },
    { value: 1048576, label: '1M' },
    { value: 2097152, label: '2M' },
];

function addRemoveOption(flag, enabled) {
    if (enabled) {
        if (!clickArgs.includes(flag)) clickArgs += (clickArgs ? ' ' : '') + flag;
    } else {
        clickArgs = clickArgs.replace(flag, '').trim();
    }
}

function updateCtxOptions() {
    const extended = document.getElementById('extendedRange').checked;
    const select = document.getElementById('ctxSelect');
    const currentValue = select.value;
    const options = extended ? CTX_EXTENDED : CTX_NORMAL;
    select.innerHTML = '';
    options.forEach(o => {
        const opt = document.createElement('option');
        opt.value = o.value;
        opt.text = o.label;
        select.add(opt);
    });
}


async function browsePath(which) {
    if (which === 'models') {
        const path = await window.pywebview.api.browse_models();
        if (path) {
            document.getElementById('modelsPath').textContent = path;
            await populateModels();
            await validatePaths();
        }
    } else {
        const path = await window.pywebview.api.browse_bin();
        if (path) {
            document.getElementById('binPath').textContent = path;
            await validatePaths();
        }
    }
}

async function resetPath(which) {
    if (which === 'models') {
        const path = await window.pywebview.api.reset_models_dir();
        document.getElementById('modelsPath').textContent = path;
        await populateModels();
        await validatePaths();
    } else {
        const path = await window.pywebview.api.reset_bin_dir();
        document.getElementById('binPath').textContent = path;
        await validatePaths();
    }
}

async function downloadModel() {
    await window.pywebview.api.download_model();
}

async function downloadBin() {
    await window.pywebview.api.download_bin();
}


async function saveCtx() {
    const value = document.getElementById('ctxSelect').value;
    await window.pywebview.api.save_pref('last_ctx', value);
}


async function saveCot() {
    const template = document.getElementById('disableCotTemplate').checked;
    await window.pywebview.api.save_pref('cot_template', template ? 'true' : 'false');
}



async function populateModels() {
    const models = await window.pywebview.api.get_models();
    const select = document.getElementById('modelSelect');
    select.innerHTML = '';
    if (models.length === 0) {
        const opt = document.createElement('option');
        opt.text = 'No .gguf files found';
        select.add(opt);
    } else {
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.file;
            opt.text = m.label;
            select.add(opt);
        });

        // Try to restore last used model
        try {
            const lastModel = await window.pywebview.api.get_last_model();
            if (lastModel) {
                const exists = Array.from(select.options).some(o => o.value === lastModel);
                if (exists) {
                    select.value = lastModel;
                }
            }
        } catch (e) {
        }
    }
}

async function updateStopOnExit() {
    const value = document.getElementById('stopOnExit').checked;
    await window.pywebview.api.set_stop_on_exit(value);
}

async function launch() {
    const model = document.getElementById('modelSelect').value;
    const ctxSize = parseInt(document.getElementById('ctxSelect').value);
    const disableCotTemplate = document.getElementById('disableCotTemplate').checked;
    const disableCotOverride = document.getElementById('disableCotOverride').checked;
    const backend = document.querySelector('input[name="backend"]:checked').value;
    let customArgs = document.getElementById('customArgs').value.trim();
    const out = document.getElementById('output');
    out.value += 'Launching ' + model + ' (' + backend + ')...\n';
    out.value += 'Context: ' + ctxSize + ' tokens\n';
    if (disableCotTemplate) out.value += 'CoT disabled via chat template\n';
    if (disableCotOverride) out.value += 'CoT disabled via forced override\n';
    if (customArgs) out.value += 'Custom args: ' + customArgs + '\n';
    out.value += 'Launched in separate window.\n';
    if (clickArgs) customArgs = (customArgs ? customArgs + ' ' : '') + clickArgs;
    await window.pywebview.api.launch(model, ctxSize, disableCotTemplate, disableCotOverride, backend, customArgs);
}

async function openHelp(section) {
    await window.pywebview.api.open_help(section);
}

async function validatePaths() {
    const out = document.getElementById('output');
    const status = await window.pywebview.api.validate_paths();
    let messages = [];
    if (!status.models_exists) messages.push('⚠ Models directory not found');
    else if (!status.models_has_files) messages.push('⚠ Models directory is empty (no .gguf files)');
    else messages.push('✓ Models directory OK (' + status.model_count + ' files)');

    if (!status.bin_exists) messages.push('⚠ Bin directory not found');
    else if (!status.has_server) messages.push('⚠ llama-server.exe not found in bin directory');
    else messages.push('✓ llama-server.exe found');

    out.value += messages.join('\n') + '\n';
}




function applyTooltips() {
    document.querySelectorAll('.info-btn').forEach(btn => {
        const onclick = btn.getAttribute('onclick');
        const match = onclick && onclick.match(/openHelp\('(.+?)'\)/);
        if (match) {
            const key = match[1];
            if (tooltips[key]) {
                btn.title = tooltips[key];
            }
        }
    });
}

async function initUI() {
    const out = document.getElementById('output');
    // Write something immediately — if this text appears in the output box
    // on the next hang, we know initUI ran but get_startup_data blocked.
    // If the box still shows the HTML default text, initUI never ran at all
    // (pywebviewready race condition).
    out.value = 'Initialising...\n';

    let data;
    try {
        const dataPromise = window.pywebview.api.get_startup_data();
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('get_startup_data timed out after 8s')), 8000)
        );
        data = await Promise.race([dataPromise, timeoutPromise]);
    } catch (e) {
        out.value += `⚠ Failed to load startup data: ${e.message}\n`;
        return;
    }

    out.value = '';

    // Paths
    document.getElementById('modelsPath').textContent = data.paths.models;
    document.getElementById('binPath').textContent = data.paths.bin;

    // Models
    const select = document.getElementById('modelSelect');
    select.innerHTML = '';
    if (data.models.length === 0) {
        const opt = document.createElement('option');
        opt.text = 'No .gguf files found';
        select.add(opt);
    } else {
        data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.file;
            opt.text = m.label;
            select.add(opt);
        });
        if (data.prefs.last_model) {
            const exists = Array.from(select.options).some(o => o.value === data.prefs.last_model);
            if (exists) select.value = data.prefs.last_model;
        }
    }

    // Context
    if (data.prefs.last_ctx) {
        const ctxSelect = document.getElementById('ctxSelect');
        const exists = Array.from(ctxSelect.options).some(o => o.value === data.prefs.last_ctx);
        if (exists) ctxSelect.value = data.prefs.last_ctx;
    }

    // CoT
    document.getElementById('disableCotTemplate').checked = data.prefs.cot_template;

    // Extras (tooltips)
    tooltips = data.extras['help-tooltips'] || {};
    applyTooltips();

    // System info
    document.getElementById('vramInfo').textContent = data.system.vram;
    document.getElementById('ramInfo').textContent = data.system.ram;

    // Validation messages
    const v = data.validation;
    let messages = [];
    if (!v.models_exists) messages.push('⚠ Models directory not found');
    else if (!v.models_has_files) messages.push('⚠ Models directory is empty (no .gguf files)');
    else messages.push('✓ Models directory OK (' + v.model_count + ' files)');
    if (!v.bin_exists) messages.push('⚠ Bin directory not found');
    else if (!v.has_server) messages.push('⚠ llama-server.exe not found in bin directory');
    else messages.push('✓ llama-server.exe found');
    out.value += messages.join('\n') + '\n';
}


// Defer by one tick to close the race window where pywebviewready fires
// between the if-check and addEventListener.
function startWhenReady() {
    if (window.pywebview && window.pywebview.api) {
        initUI();
    } else {
        window.addEventListener('pywebviewready', initUI, { once: true });
    }
}

setTimeout(startWhenReady, 0);