/* Hoja de reglajes (Mecánica): pestañas, steppers, escala de balance y
   autoguardado. Pensada para usarse con una mano en el móvil. */
(function () {
  'use strict';

  var ORDEN = ['datos', 'setup', 'piloto', 'diagnostico', 'cierre'];
  var NOMBRES = { setup: 'Setup', piloto: 'Piloto', diagnostico: 'Diagnóstico', cierre: 'Cierre', datos: 'Datos' };

  function iniciar(opts) {
    var hoja = document.getElementById('hoja');
    var form = document.getElementById('hoja-form');
    if (!hoja || !form) return;
    hoja.classList.add('js-tabs');

    // ── Pestañas ──────────────────────────────────────────
    var claveTab = 'reglajes-tab-' + opts.sesionId;
    var actual = null;
    var tabs = document.querySelectorAll('.hoja-tab');
    var btnAnt = document.getElementById('btn-ant');
    var btnSig = document.getElementById('btn-sig');
    var btnSigTxt = document.getElementById('btn-sig-txt');

    function mostrar(tab, scroll) {
      if (ORDEN.indexOf(tab) === -1) tab = 'setup';
      actual = tab;
      document.querySelectorAll('.hoja-sec').forEach(function (s) { s.classList.toggle('activa', s.dataset.tab === tab); });
      tabs.forEach(function (t) {
        var activa = t.dataset.tab === tab;
        t.classList.toggle('activa', activa);
        t.setAttribute('aria-selected', activa ? 'true' : 'false');
        if (activa && t.scrollIntoView) t.scrollIntoView({ block: 'nearest', inline: 'center' });
      });
      var i = ORDEN.indexOf(tab);
      btnAnt.disabled = i === 0;
      if (i === ORDEN.length - 1) {
        btnSigTxt.textContent = 'Terminar';
      } else {
        btnSigTxt.textContent = NOMBRES[ORDEN[i + 1]];
      }
      try { sessionStorage.setItem(claveTab, tab); } catch (e) { /* sin almacenamiento */ }
      if (scroll) window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    tabs.forEach(function (t) { t.addEventListener('click', function () { mostrar(t.dataset.tab, true); }); });
    btnAnt.addEventListener('click', function () { mostrar(ORDEN[Math.max(0, ORDEN.indexOf(actual) - 1)], true); });
    btnSig.addEventListener('click', function () {
      var i = ORDEN.indexOf(actual);
      if (i === ORDEN.length - 1) {
        guardar().then(function (ok) { if (ok) window.location = opts.verUrl; });
      } else {
        mostrar(ORDEN[i + 1], true);
      }
    });
    var inicial = opts.pestanaInicial;
    try { inicial = sessionStorage.getItem(claveTab) || inicial; } catch (e) { /* idem */ }
    if (location.hash && ORDEN.indexOf(location.hash.slice(1)) !== -1) inicial = location.hash.slice(1);
    mostrar(inicial, false);

    // ── Steppers −/+ ──────────────────────────────────────
    function decimales(paso) { var p = String(paso).split('.')[1]; return p ? p.length : 0; }
    function leer(input) {
      var v = parseFloat(String(input.value).replace(',', '.'));
      return isNaN(v) ? null : v;
    }
    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-paso-dir]');
      if (!b) return;
      var st = b.closest('.stepper');
      var input = st.querySelector('input');
      var paso = parseFloat(st.dataset.paso || '1');
      var dir = parseInt(b.dataset.pasoDir, 10);
      var valor = leer(input);
      if (valor === null) {
        // Sin valor: parte del de la sesión anterior; si no hay, de un punto
        // de inicio con sentido (clicks = 0) o abre el teclado para escribirlo.
        var antes = st.parentElement.querySelector('[data-antes]');
        var previo = antes ? parseFloat(antes.dataset.antes) : NaN;
        if (!isNaN(previo)) {
          valor = previo;
        } else if (st.dataset.inicio !== undefined) {
          valor = parseFloat(st.dataset.inicio);
        } else {
          input.focus();
          return;
        }
      } else {
        valor = valor + dir * paso;
      }
      if (st.dataset.min !== undefined) valor = Math.max(parseFloat(st.dataset.min), valor);
      if (st.dataset.max !== undefined) valor = Math.min(parseFloat(st.dataset.max), valor);
      input.value = String(parseFloat(valor.toFixed(decimales(paso))));
      input.dispatchEvent(new Event('input', { bubbles: true }));
      if (navigator.vibrate) navigator.vibrate(8);
    });
    // Clicks: no dejar pasar del máximo al escribir a mano.
    form.addEventListener('change', function (e) {
      var st = e.target.closest && e.target.closest('.stepper');
      if (!st || e.target.tagName !== 'INPUT') return;
      var v = leer(e.target);
      if (v === null) { e.target.value = ''; return; }
      if (st.dataset.min !== undefined && v < parseFloat(st.dataset.min)) e.target.value = st.dataset.min;
      if (st.dataset.max !== undefined && v > parseFloat(st.dataset.max)) e.target.value = st.dataset.max;
    });

    // Marca en naranja lo que cambia respecto a la sesión anterior.
    form.addEventListener('input', function (e) {
      var rueda = e.target.closest && e.target.closest('.rueda');
      if (!rueda) return;
      var antes = rueda.querySelector('[data-antes]');
      if (!antes || antes.dataset.antes === '') return;
      var v = leer(e.target);
      antes.classList.toggle('cambiado', v === null || v !== parseFloat(antes.dataset.antes));
    });

    // "Igualar las 4": copia Del. Izq. al resto.
    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-igualar]');
      if (!b) return;
      var clave = b.dataset.igualar;
      var origen = form.querySelector('[name="setup-' + clave + '-di"]');
      if (!origen || origen.value === '') { origen && origen.focus(); return; }
      ['dd', 'ti', 'td'].forEach(function (r) {
        var d = form.querySelector('[name="setup-' + clave + '-' + r + '"]');
        if (d) { d.value = origen.value; d.dispatchEvent(new Event('input', { bubbles: true })); }
      });
    });

    // ── Radios que se pueden desmarcar (balance, confianza, resultado) ──
    form.addEventListener('pointerdown', function (e) {
      var label = e.target.closest('label');
      var radio = label && label.querySelector('input[type=radio]');
      if (radio) radio.dataset.estabaMarcado = radio.checked ? '1' : '';
    });
    form.addEventListener('click', function (e) {
      var radio = e.target.matches && e.target.matches('input[type=radio]') ? e.target : null;
      if (!radio || radio.dataset.estabaMarcado !== '1') return;
      radio.checked = false;
      radio.dataset.estabaMarcado = '';
      radio.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // ── Lo del piloto, reflejado en la pestaña de diagnóstico ──
    function refrescarCurva(i) {
      var marcado = form.querySelector('[name="curva-' + i + '-balance"]:checked');
      var badge = hoja.querySelector('[data-bal="' + i + '"]');
      if (badge) {
        badge.className = 'bal-badge';
        if (marcado) {
          var b = parseInt(marcado.value, 10);
          badge.classList.add(b < 0 ? 'neg' : (b > 0 ? 'pos' : 'cero'));
          badge.textContent = b > 0 ? '+' + b : String(b);
        } else {
          badge.textContent = 'sin dato';
        }
      }
      var dijo = hoja.querySelector('[data-dijo="' + i + '"]');
      if (dijo) {
        dijo.textContent = '';
        form.querySelectorAll('[name="curva-' + i + '-problemas"]:checked').forEach(function (c) {
          var tag = document.createElement('span');
          tag.className = 'tag';
          tag.textContent = c.parentElement.querySelector('span').textContent;
          dijo.appendChild(tag);
        });
        var com = form.querySelector('[name="curva-' + i + '-comentario"]');
        if (com && com.value.trim()) dijo.appendChild(document.createTextNode('«' + com.value.trim() + '»'));
      }
    }
    form.addEventListener('change', function (e) { if (e.target.dataset && e.target.dataset.curva) refrescarCurva(e.target.dataset.curva); });
    form.addEventListener('input', function (e) { if (e.target.dataset && e.target.dataset.curva) refrescarCurva(e.target.dataset.curva); });
    var importante = document.getElementById('f-importante');
    if (importante) importante.addEventListener('input', function () {
      var caja = document.getElementById('diag-importante');
      document.getElementById('diag-importante-txt').textContent = importante.value;
      caja.hidden = !importante.value.trim();
    });

    // ── Mejor vuelta: "62.345", "1.02.345" o "1,02,345" → "1:02.345" ──
    function formatearVuelta(raw) {
      var t = String(raw).trim().replace(/,/g, '.').replace(/\s+/g, '');
      if (!t) return '';
      var m = t.match(/^(\d+)[:.](\d{1,2})[.:](\d{1,3})$/);
      if (m) return m[1] + ':' + ('0' + m[2]).slice(-2) + '.' + (m[3] + '00').slice(0, 3);
      if (/^\d+(\.\d+)?$/.test(t)) {
        var seg = parseFloat(t);
        if (seg >= 60) {
          var min = Math.floor(seg / 60);
          var resto = (seg - min * 60).toFixed(3);
          return min + ':' + (parseFloat(resto) < 10 ? '0' : '') + resto;
        }
        return seg.toFixed(3);
      }
      return raw;
    }
    document.querySelectorAll('[data-vuelta]').forEach(function (i) {
      i.addEventListener('change', function () { i.value = formatearVuelta(i.value); });
    });

    // ── Diagnóstico: plegar curvas sin nada que revisar ──
    hoja.querySelectorAll('.plegable').forEach(function (bloque) {
      var cab = bloque.querySelector('.curva-cab');
      cab.addEventListener('click', function () { bloque.classList.toggle('plegada'); });
      cab.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); bloque.classList.toggle('plegada'); }
      });
    });
    function revisarPliegue(i) {
      var bloque = hoja.querySelector('.plegable[data-curva-diag="' + i + '"]');
      if (!bloque) return;
      var conDato = form.querySelector('[name="curva-' + i + '-balance"]:checked:not([value="0"])') ||
                    form.querySelector('[name="curva-' + i + '-problemas"]:checked');
      if (conDato) bloque.classList.remove('plegada');
    }
    form.addEventListener('change', function (e) { if (e.target.dataset && e.target.dataset.curva) revisarPliegue(e.target.dataset.curva); });

    // ── Comentario por curva: oculto hasta que se pide ──
    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-abre-comentario]');
      if (!b) return;
      var input = form.querySelector('[name="curva-' + b.dataset.abreComentario + '-comentario"]');
      input.hidden = false;
      b.hidden = true;
      input.focus();
    });

    // ── Datos: piloto "Otro" y estado de pista rápido ──
    var selPiloto = document.getElementById('f-piloto');
    if (selPiloto) selPiloto.addEventListener('change', function () {
      document.getElementById('campo-piloto-nombre').hidden = !!selPiloto.value;
      var nombre = selPiloto.value ? selPiloto.options[selPiloto.selectedIndex].text
                                   : (document.getElementById('f-piloto-nombre').value || '—');
      document.getElementById('cab-piloto').textContent = nombre;
    });
    var pista = document.getElementById('f-pista');
    document.querySelectorAll('[data-pista]').forEach(function (b) {
      b.addEventListener('click', function () {
        var partes = pista.value.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
        var t = b.dataset.pista.toLowerCase();
        var i = partes.map(function (x) { return x.toLowerCase(); }).indexOf(t);
        if (i === -1) partes.push(b.dataset.pista); else partes.splice(i, 1);
        pista.value = partes.join(', ');
        pista.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });

    // ── Autoguardado ──────────────────────────────────────
    var indicador = document.getElementById('estado-guardado');
    var temporizador = null, enVuelo = null, pendiente = false, sinGuardar = false;
    var TEXTOS = {
      ok: ['bi-cloud-check', 'Guardado'],
      pendiente: ['bi-pencil', 'Cambios sin guardar'],
      guardando: ['bi-arrow-repeat', 'Guardando…'],
      error: ['bi-wifi-off', 'Sin guardar · reintentando']
    };
    function estado(e, hora) {
      indicador.dataset.estado = e;
      indicador.innerHTML = '';
      var ic = document.createElement('i'); ic.className = 'bi ' + TEXTOS[e][0];
      var tx = document.createElement('span'); tx.textContent = TEXTOS[e][1];
      indicador.appendChild(ic); indicador.appendChild(tx);
      if (hora) {
        var h = document.createElement('span'); h.className = 'hora'; h.textContent = hora.slice(0, 5);
        indicador.appendChild(h);
      }
    }
    function programar() {
      sinGuardar = true;
      estado('pendiente');
      clearTimeout(temporizador);
      temporizador = setTimeout(guardar, 900);
    }
    form.addEventListener('input', programar);
    form.addEventListener('change', programar);

    function renovarToken() {
      return fetch(location.pathname, { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (html) {
        var m = html.match(/name="csrf_token" value="([^"]+)"/);
        if (!m) throw new Error('sin token');
        document.querySelectorAll('input[name="csrf_token"]').forEach(function (i) { i.value = m[1]; });
      });
    }
    function enviar(reintento) {
      return fetch(location.pathname, {
        method: 'POST', body: new FormData(form), credentials: 'same-origin', keepalive: true,
        headers: { 'X-Requested-With': 'fetch' }
      }).then(function (r) {
        if (r.status === 400 && !reintento) return renovarToken().then(function () { return enviar(true); });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
    }
    function guardar() {
      clearTimeout(temporizador);
      if (enVuelo) { pendiente = true; return enVuelo; }
      estado('guardando');
      pendiente = false;
      enVuelo = enviar(false).then(function (d) {
        sinGuardar = false;
        estado('ok', d.guardado);
        Object.keys(d.progreso || {}).forEach(function (k) {
          var p = document.querySelector('[data-punto="' + k + '"]');
          if (p) p.classList.toggle('lleno', !!d.progreso[k]);
        });
        return true;
      }).catch(function () {
        estado('error');
        temporizador = setTimeout(guardar, 5000);
        return false;
      }).then(function (ok) {
        enVuelo = null;
        if (pendiente) return guardar();
        return ok;
      });
      return enVuelo;
    }
    document.getElementById('btn-guardar').addEventListener('click', function () { guardar(); });
    form.addEventListener('submit', function (e) { e.preventDefault(); guardar(); });
    // Al cambiar de app o bloquear el móvil, se guarda ya.
    document.addEventListener('visibilitychange', function () { if (document.hidden && sinGuardar) guardar(); });
    window.addEventListener('beforeunload', function (e) {
      if (sinGuardar) { guardar(); e.preventDefault(); e.returnValue = ''; }
    });
    // Intro en un campo de texto no envía la página.
    form.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.tagName === 'INPUT') { e.preventDefault(); e.target.blur(); }
    });
  }

  window.HojaReglajes = { iniciar: iniciar };
})();
