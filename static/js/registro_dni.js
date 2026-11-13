(() => {
    const dniInput = document.getElementById('dni');
    const mensaje = document.getElementById('mensaje-reniec');
    const token = document.getElementById('validacion-dni');
    const form = dniInput.form;
    const submit = form.querySelector('button[type="submit"]');
    const campos = ['nombres', 'apellido_paterno', 'apellido_materno'].map(id => document.getElementById(id));
    let consulta = null;
    let version = 0;
    let temporizador;
    let dniValidado = '';

    function limpiarIdentidad() {
        ++version;
        clearTimeout(temporizador);
        consulta?.abort();
        consulta = null;
        dniValidado = '';
        token.value = '';
        campos.forEach(campo => campo.value = '');
        submit.disabled = true;
        dniInput.setCustomValidity('Consulta tu DNI para completar los datos antes de registrarte.');
        mensaje.className = 'registration-reniec-message';
    }

    async function buscarDNI() {
        limpiarIdentidad();
        const dni = dniInput.value.replace(/[^0-9]/g, '').slice(0, 8);
        dniInput.value = dni;
        if (!/^[0-9]{8}$/.test(dni)) {
            mensaje.classList.add('is-warning');
            mensaje.textContent = dni ? 'Completa los 8 dígitos del DNI.' : '';
            return;
        }
        const actual = version;
        consulta = new AbortController();
        mensaje.classList.add('is-loading');
        mensaje.textContent = 'Buscando datos del DNI…';
        try {
            const response = await fetch('/api/reniec/' + encodeURIComponent(dni), {
                signal: consulta.signal,
                cache: 'no-store',
            });
            const datos = await response.json();
            if (actual !== version || dniInput.value !== dni) return;
            if (!response.ok || !datos.ok) throw new Error(datos.mensaje || 'No pudimos consultar el DNI.');
            if (datos.dni !== dni || !datos.validacion_dni || !campos.every(campo => datos[campo.id])) {
                throw new Error('La consulta no devolvió los datos completos de este DNI. Vuelve a buscarlo.');
            }
            campos.forEach(campo => campo.value = datos[campo.id]);
            token.value = datos.validacion_dni;
            dniValidado = dni;
            dniInput.setCustomValidity('');
            submit.disabled = false;
            mensaje.className = 'registration-reniec-message is-success';
            mensaje.textContent = 'Datos encontrados correctamente.';
        } catch (error) {
            if (actual !== version || error.name === 'AbortError') return;
            mensaje.className = 'registration-reniec-message is-error';
            mensaje.textContent = error.message || 'Error al consultar el DNI.';
        }
    }

    dniInput.addEventListener('input', () => {
        limpiarIdentidad();
        dniInput.value = dniInput.value.replace(/[^0-9]/g, '').slice(0, 8);
        mensaje.textContent = dniInput.value ? 'Completa los 8 dígitos del DNI.' : '';
        if (dniInput.value.length === 8) {
            mensaje.textContent = 'Consultando el nuevo DNI…';
            temporizador = setTimeout(buscarDNI, 300);
        }
    });
    form.addEventListener('submit', event => {
        if (dniInput.value !== dniValidado || !token.value) {
            event.preventDefault();
            limpiarIdentidad();
            mensaje.textContent = 'Consulta el DNI actual antes de registrarte.';
            dniInput.reportValidity();
        }
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted) buscarDNI();
    });
    limpiarIdentidad();
    mensaje.textContent = '';
    if (dniInput.value) buscarDNI();
})();
