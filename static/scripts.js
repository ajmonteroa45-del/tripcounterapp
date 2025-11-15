/* =========================================================
   scripts.js: Lógica de Interacción con la API de Flask
   ========================================================= */

// --- Utilidad ---
function formatCurrency(value) {
    return `S/${parseFloat(value).toFixed(2)}`;
}

// =========================================================
// INICIALIZACIÓN GLOBAL SEGURA
// =========================================================

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Inicializar todas las páginas solo si el elemento clave existe.
    if (document.getElementById('trip-form')) initializeTripsPage();
    if (document.getElementById('expense-form')) initializeExpensesPage();
    
    // CORRECCIÓN: Llamamos a la función SOLO si el formulario principal existe
    if (document.getElementById('add-presupuesto-form')) initializeBudgetPage();
    
    if (document.getElementById('km-state-container')) initializeKilometrajePage(); // NUEVA FUNCIÓN: Inicializar Kilometraje
    if (document.getElementById('extra-form')) initializeExtrasPage();
    if (document.getElementById('summary_fecha')) initializeSummaryPage(); 
    if (document.getElementById('reportForm')) initializeReportPage();
    
    // 2. Inicializar recordatorios de la Home
    if (document.querySelector('.mark-paid-btn')) initializeHomeReminders(); 

    // 3. Escucha global de cambio de fecha (si el input existe)
    const fechaInput = document.getElementById('fecha'); // Usado por Viajes y Gastos
    const fechaExtraInput = document.getElementById('fecha_extra'); 
    const fechaKmInput = document.getElementById('fecha_km'); // NUEVO: para Kilometraje
    
    // Listener para Viajes y Gastos
    if (fechaInput) {
        fechaInput.addEventListener('change', () => {
            if (document.getElementById('trip-form')) fetchAndDisplayTrips(fechaInput.value);
            if (document.getElementById('expense-form')) fetchAndDisplayExpenses(fechaInput.value);
        });
    }
    
    // Listener para Extras
    if (fechaExtraInput) {
         fechaExtraInput.addEventListener('change', () => {
            if (document.getElementById('extra-form')) fetchAndDisplayExtras(fechaExtraInput.value);
        });
    }

    // Listener para Kilometraje
    if (fechaKmInput) { 
         fechaKmInput.addEventListener('change', () => {
            if (document.getElementById('km-state-container')) fetchAndDisplayKM(fechaKmInput.value);
        });
    }
});


// =========================================================
// LÓGICA DE VIAJES (TRIPS)
// =========================================================

function initializeTripsPage() {
    const tripForm = document.getElementById('trip-form');
    const tripsListDiv = document.getElementById('trips-list');
    
    // Función de renderizado (GET)
    async function fetchAndDisplayTrips(date) {
        if (tripsListDiv) tripsListDiv.innerHTML = 'Cargando viajes...';
        try {
            const response = await fetch(`/api/trips?date=${date}`, {credentials: 'include'});
            const data = await response.json();
            
            if (response.status !== 200) {
                if (tripsListDiv) tripsListDiv.innerHTML = `<div class="message-box error">Error al cargar viajes: ${data.error || 'API Error'}</div>`;
                return;
            }

            const trips = data.trips;
            const bonus = parseFloat(data.bonus || 0); 
            
            let html = '';
            
            if (trips.length > 0) {
                html += `
                    <p>Total de servicios hoy: <strong>${trips.length}</strong></p>
                    <table class="table table-striped summary-table">
                        <thead>
                            <tr><th>#</th><th>Inicio</th><th>Fin</th><th>Monto</th><th>Propina</th><th>Aerop.</th><th>Total</th></tr>
                        </thead>
                        <tbody>
                `;
                let totalMonto = 0;
                let totalPropina = 0;
                let totalDiaViajes = 0; 

                trips.forEach(trip => {
                    const monto = parseFloat(trip.Monto);
                    const propina = parseFloat(trip.Propina);
                    const rowTotal = parseFloat(trip.Total);
                    
                    totalMonto += monto;
                    totalPropina += propina;
                    totalDiaViajes += rowTotal;
                    
                    html += `
                        <tr>
                            <td>${trip.Numero}</td>
                            <td>${trip['Hora inicio']}</td>
                            <td>${trip['Hora fin']}</td>
                            <td>${formatCurrency(monto)}</td>
                            <td>${formatCurrency(propina)}</td>
                            <td>${trip.Aeropuerto > 0 ? 'S/6.50' : 'No'}</td>
                            <td><strong>${formatCurrency(rowTotal)}</strong></td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table>`;

                const totalFinalDia = totalDiaViajes + bonus;

                html += `
                    <hr>
                    <div class="card p-3 mt-3">
                        <h4>Resumen de Ingresos</h4>
                        <p>Monto base: <strong>${formatCurrency(totalMonto)}</strong></p>
                        <p>Propina total: <strong>${formatCurrency(totalPropina)}</strong></p>
                        <p>Subtotal (sin Bono): <strong>${formatCurrency(totalDiaViajes)}</strong></p>
                        <h4>💰 Bono: <strong class="text-success">${formatCurrency(bonus)}</strong></h4>
                        <hr>
                        <p class="h4">Total de Ingresos del Día: <strong class="text-primary">${formatCurrency(totalFinalDia)}</strong></p>
                    </div>
                `;

            } else {
                html = '<div class="message-box alert alert-warning">Aún no hay viajes registrados para este día.</div>';
            }
            
            if (tripsListDiv) tripsListDiv.innerHTML = html;


        } catch (error) {
            console.error('Error al cargar los viajes:', error);
            if (tripsListDiv) tripsListDiv.innerHTML = '<div class="message-box alert alert-danger">Error al conectar con la API de viajes.</div>';
        }
    }

    // Manejar el envío del formulario (POST)
    tripForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: tripForm.fecha.value,
            hora_inicio: tripForm.hora_inicio.value,
            hora_fin: tripForm.hora_fin.value,
            monto: parseFloat(tripForm.monto.value),
            propina: parseFloat(tripForm.propina.value || 0),
            aeropuerto: tripForm.aeropuerto.checked
        };
        
        try {
            const response = await fetch('/api/trips', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data),
                credentials: 'include'
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`Viaje #${result.trip.Numero} registrado. Bono total actualizado a ${formatCurrency(result.new_bonus)}.`);
                
                tripForm.hora_inicio.value = '';
                tripForm.hora_fin.value = '';
                tripForm.monto.value = '';
                tripForm.propina.value = '0';
                tripForm.aeropuerto.checked = false;
                
                fetchAndDisplayTrips(data.fecha);
            } else {
                alert(`Error al registrar el viaje: ${result.error || response.statusText}`);
            }
            
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    });
    
    // Inicializar
    fetchAndDisplayTrips(document.getElementById('fecha').value);
}

// =========================================================
// LÓGICA DE EXTRAS
// =========================================================

function initializeExtrasPage() {
    const extraForm = document.getElementById('extra-form');
    const extrasListDiv = document.getElementById('extras-list');
    const fechaExtraInput = document.getElementById('fecha_extra'); 
    
    if (!extraForm || !extrasListDiv || !fechaExtraInput) return;

    fetchAndDisplayExtras(fechaExtraInput.value); 

    // Función de renderizado (GET)
    async function fetchAndDisplayExtras(date) {
        extrasListDiv.innerHTML = 'Cargando viajes extra...';
        try {
            const response = await fetch(`/api/extras?date=${date}`, {credentials: 'include'});
            const extras = await response.json();
            
            if (response.status !== 200) {
                extrasListDiv.innerHTML = `<div class="message-box alert alert-danger">Error al cargar extras: ${extras.error || 'API Error'}</div>`;
                return;
            }
            
            let html = '';
            let totalMonto = 0;
            
            if (extras.length > 0) {
                 html += `
                    <p>Total de viajes extra hoy: <strong>${extras.length}</strong></p>
                    <table class="table table-striped summary-table">
                        <thead>
                            <tr><th>#</th><th>Inicio</th><th>Fin</th><th>Monto</th><th>Total</th></tr>
                        </thead>
                        <tbody>
                `;
                
                extras.forEach(extra => {
                    const monto = parseFloat(extra.Monto);
                    totalMonto += monto;
                    
                    html += `
                        <tr>
                            <td>${extra.Numero}</td>
                            <td>${extra['Hora inicio']}</td>
                            <td>${extra['Hora fin']}</td>
                            <td>${formatCurrency(monto)}</td>
                            <td><strong>${formatCurrency(extra.Total)}</strong></td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table>`;

                html += `
                    <hr>
                    <div class="card p-3 mt-3">
                        <p class="h4">Total Ingresos Extra del Día: <strong class="text-primary">${formatCurrency(totalMonto)}</strong></p>
                    </div>
                `;
            } else {
                html = '<div class="message-box alert alert-warning">Aún no hay viajes extra registrados para este día.</div>';
            }
            
            extrasListDiv.innerHTML = html;

        } catch (error) {
            console.error('Error al cargar los extras:', error);
            extrasListDiv.innerHTML = '<div class="message-box alert alert-danger">Error al conectar con la API de extras.</div>';
        }
    }

    // Manejar el envío del formulario (POST)
    extraForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: extraForm.fecha_extra.value, // Usar fecha_extra
            hora_inicio: extraForm.hora_inicio_extra.value,
            hora_fin: extraForm.hora_fin_extra.value,
            monto: parseFloat(extraForm.monto_extra.value),
        };
        
        try {
            const response = await fetch('/api/extras', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data),
                credentials: 'include'
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`Viaje Extra #${result.extra.Numero} registrado.`);
                
                extraForm.hora_inicio_extra.value = '';
                extraForm.hora_fin_extra.value = '';
                extraForm.monto_extra.value = '';
                
                fetchAndDisplayExtras(data.fecha);
            } else {
                alert(`Error al registrar el viaje extra: ${result.error || response.statusText}`);
            }
            
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    });
}


// =========================================================
// LÓGICA DE GASTOS (EXPENSES)
// =========================================================

function initializeExpensesPage() {
    const expenseForm = document.getElementById('expense-form');
    const expensesListDiv = document.getElementById('expenses-list');
    const fechaInput = document.getElementById('fecha'); 
    
    if (!expenseForm || !expensesListDiv || !fechaInput) return;

    fetchAndDisplayExpenses(fechaInput.value); 

    // Función de renderizado (GET)
    async function fetchAndDisplayExpenses(date) {
        expensesListDiv.innerHTML = 'Cargando gastos...';
        try {
            const response = await fetch(`/api/expenses?date=${date}`, {credentials: 'include'});
            const expenses = await response.json();
            
            if (response.status !== 200) {
                expensesListDiv.innerHTML = `<div class="message-box alert alert-danger">Error al cargar gastos: ${expenses.error || 'API Error'}</div>`;
                return;
            }
            
            let html = '';
            let totalGasto = 0;
            
            if (expenses.length > 0) {
                 html += `
                    <p>Total de gastos registrados hoy: <strong>${expenses.length}</strong></p>
                    <table class="table table-striped summary-table">
                        <thead>
                            <tr><th>Hora</th><th>Monto</th><th>Categoría</th><th>Descripción</th></tr>
                        </thead>
                        <tbody>
                `;
                
                expenses.forEach(expense => {
                    const monto = parseFloat(expense.Monto);
                    totalGasto += monto;
                    
                    html += `
                        <tr>
                            <td>${expense.Hora}</td>
                            <td>${formatCurrency(monto)}</td>
                            <td>${expense.Categoría}</td>
                            <td>${expense.Descripción}</td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table>`;

                html += `
                    <hr>
                    <div class="card p-3 mt-3">
                        <p class="h4">Total Gastos del Día: <strong class="text-danger">${formatCurrency(totalGasto)}</strong></p>
                    </div>
                `;
            } else {
                html = '<div class="message-box alert alert-warning">Aún no hay gastos registrados para este día.</div>';
            }
            
            expensesListDiv.innerHTML = html;

        } catch (error) {
            console.error('Error al cargar los gastos:', error);
            expensesListDiv.innerHTML = '<div class="message-box alert alert-danger">Error al conectar con la API de gastos.</div>';
        }
    }

    // Manejar el envío del formulario (POST)
    expenseForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: expenseForm.fecha.value,
            hora: expenseForm.hora.value,
            monto: parseFloat(expenseForm.monto.value),
            categoria: expenseForm.categoria.value,
            descripcion: expenseForm.descripcion.value,
        };
        
        try {
            const response = await fetch('/api/expenses', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data),
                credentials: 'include'
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`Gasto en ${data.categoria} de ${formatCurrency(data.monto)} registrado.`);
                
                // Limpiar solo los campos de monto/categoría/descripción, manteniendo fecha/hora
                expenseForm.monto.value = '';
                expenseForm.categoria.value = '';
                expenseForm.descripcion.value = '';
                
                fetchAndDisplayExpenses(data.fecha);
            } else {
                alert(`Error al registrar el gasto: ${result.message || result.error || response.statusText}`);
            }
            
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    });
}


// =========================================================
// LÓGICA DE KILOMETRAJE (NUEVA IMPLEMENTACIÓN)
// =========================================================

function initializeKilometrajePage() {
    const kmFormStart = document.getElementById('km-start-form');
    const kmFormEnd = document.getElementById('km-end-form');
    const kmStateContainer = document.getElementById('km-state-container');
    const fechaKmInput = document.getElementById('fecha_km');

    if (!kmFormStart || !kmFormEnd || !kmStateContainer || !fechaKmInput) return;

    // Carga inicial
    fetchAndDisplayKM(fechaKmInput.value); 

    // Función de renderizado (GET)
    async function fetchAndDisplayKM(date) {
        kmStateContainer.innerHTML = 'Cargando estado de kilometraje...';
        
        try {
            const response = await fetch(`/api/kilometraje?date=${date}`, {credentials: 'include'});
            const data = await response.json();
            
            // Ocultar ambos formularios inicialmente
            kmFormStart.style.display = 'none';
            kmFormEnd.style.display = 'none';

            if (response.status === 200 && data.status === "no_record") {
                // Caso 1: No hay registro (Mostrar START)
                kmStateContainer.innerHTML = '<div class="alert alert-info">No se ha iniciado el registro de KM.</div>';
                kmFormStart.style.display = 'block';
                kmFormEnd.style.display = 'none';
            } else if (response.ok && data.hasOwnProperty('KM Inicio')) {
                const kmInicio = parseInt(data['KM Inicio']);
                const kmFin = data['KM Fin'];
                const recorrido = data.Recorrido;
                
                let html = `
                    <div class="card bg-light p-3">
                        <p>KM de Inicio: <strong>${kmInicio}</strong></p>
                        <p>Notas: ${data.Notas || 'N/A'}</p>
                `;

                if (kmFin) {
                    // Caso 3: Registro Completo
                    html += `
                        <p>KM Final: <strong class="text-success">${kmFin}</strong></p>
                        <h3>Recorrido Total: <strong class="text-primary">${recorrido} KM</strong></h3>
                    `;
                    kmFormStart.style.display = 'none';
                    kmFormEnd.style.display = 'none';
                } else {
                    // Caso 2: Registro Iniciado (Mostrar END)
                    html += `<div class="alert alert-warning">KM Final Pendiente.</div>`;
                    kmFormEnd.style.display = 'block';
                    // Asegura que el KM final no sea menor al inicial
                    document.getElementById('km_value_end').min = kmInicio; 
                }

                html += `</div>`;
                kmStateContainer.innerHTML = html;
            } else {
                 kmStateContainer.innerHTML = `<div class="alert alert-danger">Error al cargar datos: ${data.error || 'Error API'}</div>`;
            }

        } catch (error) {
            console.error('Error al cargar KM:', error);
            kmStateContainer.innerHTML = '<div class="alert alert-danger">Error de conexión al servidor de Kilometraje.</div>';
        }
    }

    // Manejar el envío de formularios (POST)
    const handleKmSubmit = async (e, action) => {
        e.preventDefault();
        
        const form = e.target;
        const kmValue = form.querySelector('input[name="km_value"]').value;
        // Asumiendo que solo el formulario de inicio tiene campo 'notas' con ID 'notas_start'
        const notas = document.getElementById('notas_start') ? document.getElementById('notas_start').value : ''; 
        
        if (!kmValue) {
            alert("Debe ingresar un valor de kilometraje.");
            return;
        }

        const data = {
            km_value: kmValue,
            action: action,
            fecha: fechaKmInput.value,
            notas: notas
        };
        
        try {
            const response = await fetch('/api/kilometraje', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data),
                credentials: 'include'
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(action === 'start' ? `KM de inicio ${result.km_inicio} registrado.` : `KM de fin ${result.km_fin} registrado. Recorrido: ${result.recorrido} KM.`);
                fetchAndDisplayKM(data.fecha);
                form.reset();
            } else {
                alert(`Error al registrar KM: ${result.message || result.error || response.statusText}`);
            }
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    };

    kmFormStart.addEventListener('submit', (e) => handleKmSubmit(e, 'start'));
    kmFormEnd.addEventListener('submit', (e) => handleKmSubmit(e, 'end'));
}


// =========================================================
// LÓGICA DE PRESUPUESTO (CORRECCIÓN CRÍTICA DE TYPEERROR)
// =========================================================

function initializeBudgetPage() {
    const PRESUPUESTO_API_URL = '/api/presupuesto';
    const budgetForm = document.getElementById('add-presupuesto-form'); 
    const budgetListContainer = document.getElementById('presupuesto-table'); 
    const budgetMessageDiv = document.getElementById('budget-message'); 

    // --- Validación de elementos críticos ---
    if (!budgetForm || !budgetListContainer || !budgetMessageDiv) {
        console.error("Error: Elementos principales del Presupuesto no encontrados.");
        // Este error ocurre si la función se llama en una página que no es presupuesto
        return;
    }
    
    // --- Lógica Fijo/Variable (CORRECCIÓN CRÍTICA: Se corrige el TypeError) ---
    const fijoRadio = document.getElementById('gasto_fijo');
    const variableRadio = document.getElementById('gasto_variable');
    const fechaContainer = document.getElementById('fecha-pago-container');
    const fechaInput = document.getElementById('fecha_pago');
    
    // CORRECCIÓN CLAVE: Solo si *todos* los elementos condicionales existen, adjuntamos listeners.
    if (fijoRadio && variableRadio && fechaContainer && fechaInput) { 
        function toggleFechaInput() {
            if (fijoRadio.checked) {
                fechaContainer.style.display = 'block';
                fechaInput.setAttribute('required', 'required');
            } else {
                fechaContainer.style.display = 'none';
                fechaInput.removeAttribute('required');
            }
        }
        
        fijoRadio.addEventListener('change', toggleFechaInput);
        variableRadio.addEventListener('change', toggleFechaInput);
        toggleFechaInput(); // Inicializar el estado
    }
    // ---------------------------------------------------------------------------------


    // 3. Función para Cargar y Renderizar Presupuestos (GET)
    async function loadBudgets() {
        const tableBody = budgetListContainer.querySelector('tbody');
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="6" class="text-center">Cargando presupuestos...</td></tr>';

        try {
            const response = await fetch(PRESUPUESTO_API_URL, { method: 'GET', credentials: 'include'});
            const records = await response.json();

            if (!response.ok) {
                if (tableBody) tableBody.innerHTML = `<tr><td colspan="6" class="message-box error">❌ Error al cargar datos: ${records.error || 'No autorizado.'}</td></tr>`;
                return;
            }

            if (tableBody) {
                if (records.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No hay ítems de presupuesto registrados.</td></tr>';
                    return;
                }
                
                tableBody.innerHTML = '';
                
                records.forEach((r, i) => {
                    const rowIndex = i + 2; 
                    const isPaid = r.pagado === true || r.pagado === 'True' || r.pagado === 'TRUE';
                    
                    const row = tableBody.insertRow();
                    row.innerHTML = `
                        <td>${r.categoria}</td>
                        <td>${formatCurrency(r.monto)}</td>
                        <td>${r.tipo || 'N/A'}</td> <td>${r.fecha_pago || 'N/A'}</td>
                        <td>${isPaid ? '✅ SÍ' : '❌ NO'}</td>
                        <td>
                            ${isPaid ? 
                                `<span class="text-success me-2">Pagado</span>` : 
                                `<button class="btn btn-sm btn-info mark-paid-btn me-2" data-row-index="${rowIndex}">Marcar</button>`
                            }
                            <button class="btn btn-sm btn-danger delete-btn" data-row-index="${rowIndex}">
                                Eliminar
                            </button>
                        </td>
                    `;
                });
            }

        } catch (error) {
            console.error('Error al cargar la lista de presupuestos:', error);
            if (tableBody) tableBody.innerHTML = '<tr><td colspan="6" class="message-box error">❌ No se pudo conectar con la API de presupuestos.</td></tr>';
        }
    }

    // 2. Manejo del Formulario (POST: Crear nuevo presupuesto)
    budgetForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        budgetMessageDiv.innerHTML = 'Procesando...';
        budgetMessageDiv.className = '';

        // Aseguramos que los radios existan antes de acceder a ellos
        const tipoGasto = document.querySelector('input[name="tipo_gasto"]:checked') ? document.querySelector('input[name="tipo_gasto"]:checked').value : 'N/A';
        let fechaPago = '';

        if (tipoGasto === 'Fijo' && fechaInput) {
            fechaPago = fechaInput.value;
            if (!fechaPago) {
                budgetMessageDiv.innerHTML = '❌ Error: El gasto fijo requiere una fecha de pago.';
                budgetMessageDiv.className = 'message-box alert alert-danger';
                return;
            }
        }

        const data = {
            categoria: document.getElementById('categoria').value,
            monto: document.getElementById('monto').value,
            tipo_gasto: tipoGasto,
            fecha_pago: fechaPago
        };
        
        try {
            const response = await fetch(PRESUPUESTO_API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
                credentials: 'include'
            });

            const result = await response.json();

            if (response.ok && result.status === 'ok') {
                budgetMessageDiv.innerHTML = '✅ ¡Presupuesto añadido con éxito!';
                budgetMessageDiv.className = 'message-box alert alert-success';
                budgetForm.reset(); 
                if (fijoRadio) fijoRadio.checked = true; // Reiniciar Fijo/Variable
                if (fechaInput) toggleFechaInput(); // Aplicar la visibilidad
                loadBudgets(); 
            } else {
                const msg = result.message || result.error || 'Error al añadir presupuesto.';
                budgetMessageDiv.innerHTML = `❌ Error: ${msg}`;
                budgetMessageDiv.className = 'message-box alert alert-danger';
            }
        } catch (error) {
            console.error('Error al enviar el formulario:', error);
            budgetMessageDiv.innerHTML = '❌ Error de conexión con el servidor.';
            budgetMessageDiv.className = 'message-box alert alert-danger';
        }
    });

    // 4. Asignar Event Listeners para PUT (Marcar Pagado) y DELETE (Eliminar)
    if (budgetListContainer) {
        budgetListContainer.addEventListener('click', async (event) => {
            const target = event.target;
            const rowIndex = target.dataset.rowIndex;
            if (!rowIndex) return;

            if (target.classList.contains('mark-paid-btn')) {
                // Lógica Marcar como Pagado (PUT)
                if (!confirm('¿Marcar este ítem como pagado?')) return;
                
                target.disabled = true;
                target.textContent = 'Actualizando...';
                
                try {
                    const response = await fetch(PRESUPUESTO_API_URL, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ row_index: rowIndex }),
                        credentials: 'include'
                    });
                    
                    const result = await response.json();

                    if (response.ok && result.status === 'ok') {
                        loadBudgets(); 
                    } else {
                        alert(`Error al marcar como pagado: ${result.error || 'Error desconocido'}`);
                    }
                } catch (error) {
                    console.error('Error en la conexión:', error);
                    alert('Error de conexión o servidor.');
                }
            } else if (target.classList.contains('delete-btn')) {
                // Lógica Eliminar (DELETE)
                if (!confirm('¿Estás seguro de que quieres eliminar esta categoría de presupuesto? Esta acción es permanente.')) return;

                target.disabled = true;
                target.textContent = 'Eliminando...';
                
                try {
                    const response = await fetch(PRESUPUESTO_API_URL, {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ row_index: rowIndex }),
                        credentials: 'include'
                    });
                    
                    const result = await response.json();

                    if (response.ok && result.status === 'ok') {
                        loadBudgets(); 
                    } else {
                        alert(`Error al eliminar: ${result.message || result.error || 'Error desconocido'}`);
                    }
                } catch (error) {
                    console.error('Error en la conexión:', error);
                    alert('Error de conexión o servidor.');
                }
            }
        });
    }
    
    // Ejecutar carga inicial
    loadBudgets();
}


// =========================================================
// LÓGICA DE RECORDATORIOS HOME
// =========================================================

function initializeHomeReminders() {
    const PRESUPUESTO_API_URL = '/api/presupuesto';
    const paidButtons = document.querySelectorAll('.mark-paid-btn');
    
    const handleHomeAction = async (event, method) => {
        const target = event.target;
        const row_index = target.dataset.rowIndex;
        const category = target.dataset.category;
        
        if (!row_index) return;
        
        let confirmMsg = '';
        if (method === 'PUT') {
            confirmMsg = `¿Estás seguro de que quieres marcar "${category}" como pagado?`;
        } else {
            return;
        }

        if (!confirm(confirmMsg)) return;

        target.disabled = true;
        target.textContent = 'Actualizando...';
        
        try {
            const response = await fetch(PRESUPUESTO_API_URL, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ row_index: row_index }),
                credentials: 'include'
            });
            
            const data = await response.json();

            if (response.ok && data.status === 'ok') {
                const listItem = target.closest('li');
                if (listItem) {
                    listItem.style.opacity = '0.5';
                    listItem.innerHTML = `✅ ${category} marcado como pagado. (Recarga la página)`;
                }
            } else {
                alert(`Error al marcar como pagado: ${data.error || 'Error desconocido'}`);
                target.textContent = 'Marcar como pagado';
                target.disabled = false;
            }
        } catch (error) {
            console.error('Error en la conexión:', error);
            alert('Error de conexión o servidor al intentar actualizar el pago.');
            target.textContent = 'Marcar como pagado';
            target.disabled = false;
        }
    };
    
    paidButtons.forEach(button => {
        button.addEventListener('click', (e) => handleHomeAction(e, 'PUT'));
    });
    
}


// --- FUNCIONES DE INICIALIZACIÓN PENDIENTES (Placeholders que ya no están vacíos) ---

function initializeSummaryPage() {}
function initializeReportPage() {}
