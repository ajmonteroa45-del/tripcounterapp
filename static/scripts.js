/* =========================================================
   scripts.js: Lógica de Interacción con la API de Flask
   ========================================================= */

// --- Utilidad (Hecha Global para ser accesible desde cualquier plantilla HTML) ---
function formatCurrency(value) {
    return `S/${parseFloat(value).toFixed(2)}`;
}

// =========================================================
// INICIALIZACIÓN GLOBAL SEGURA
// =========================================================

document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Inicializar todas las páginas solo si el elemento clave existe.
    // NOTA: Toda la lógica de listeners de fecha se mueve dentro de estas funciones.
    if (document.getElementById('trip-form')) initializeTripsPage();
    if (document.getElementById('expense-form')) initializeExpensesPage(); 
    if (document.getElementById('add-presupuesto-form')) initializeBudgetPage();
    if (document.getElementById('km-state-container')) initializeKilometrajePage(); 
    if (document.getElementById('extra-form')) initializeExtrasPage(); 
    if (document.getElementById('summary_fecha')) initializeSummaryPage(); 
    if (document.getElementById('reportForm')) initializeReportPage();
    
    // 2. Inicializar recordatorios de la Home
    if (document.querySelector('.mark-paid-btn')) initializeHomeReminders(); 
    
    // ELIMINADO: Bloque 3 de escucha global de fechas (Causaba errores de ámbito).
});


// =========================================================
// LÓGICA DE VIAJES (TRIPS) - AUTÓNOMA
// =========================================================

function initializeTripsPage() {
    const tripForm = document.getElementById('trip-form');
    const tripsListDiv = document.getElementById('trips-list');
    const fechaInput = document.getElementById('fecha_viaje'); 

    if (!tripForm || !tripsListDiv || !fechaInput) return;
    
    // Función de renderizado (GET) - LOCAL
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

    // ** Listener del cambio de fecha (LOCAL) **
    fechaInput.addEventListener('change', (e) => {
        fetchAndDisplayTrips(e.target.value);
    });

    // Manejar el envío del formulario (POST)
    tripForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: fechaInput.value, 
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
    
    // Inicializar con la fecha actual
    fetchAndDisplayTrips(fechaInput.value);
}

// =========================================================
// LÓGICA DE EXTRAS - AUTÓNOMA (CORREGIDO)
// =========================================================

function initializeExtrasPage() {
    const extraForm = document.getElementById('extra-form');
    const extrasListDiv = document.getElementById('extras-list');
    const fechaExtraInput = document.getElementById('fecha_extra'); 
    
    if (!extraForm || !extrasListDiv || !fechaExtraInput) return;

    // Función de renderizado (GET) - LOCAL
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

    // ** Listener del cambio de fecha (LOCAL) **
    fechaExtraInput.addEventListener('change', (e) => {
        fetchAndDisplayExtras(e.target.value);
    });

    // Carga inicial
    fetchAndDisplayExtras(fechaExtraInput.value);

    // Manejar el envío del formulario (POST)
    extraForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: fechaExtraInput.value, 
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
// LÓGICA DE GASTOS (EXPENSES) - AUTÓNOMA (CORREGIDO)
// =========================================================

function initializeExpensesPage() {
    const expenseForm = document.getElementById('expense-form');
    const expensesListDiv = document.getElementById('expenses-list');
    const fechaInput = document.getElementById('fecha_gasto'); // ID único para gastos
    
    if (!expenseForm || !expensesListDiv || !fechaInput) return;

    // Función de renderizado (GET) - LOCAL
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
    
    // ** Listener del cambio de fecha (LOCAL) **
    fechaInput.addEventListener('change', (e) => {
        fetchAndDisplayExpenses(e.target.value);
    });
    
    // Carga inicial
    fetchAndDisplayExpenses(fechaInput.value);

    // Manejar el envío del formulario (POST)
    expenseForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: expenseForm.fecha_gasto.value,
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
// LÓGICA DE KILOMETRAJE - AUTÓNOMA (CORREGIDO)
// =========================================================

function initializeKilometrajePage() {
    const kmFormStart = document.getElementById('km-start-form');
    const kmFormEnd = document.getElementById('km-end-form');
    const kmStateContainer = document.getElementById('km-state-container');
    const fechaKmInput = document.getElementById('fecha_km');
    const summaryBtn = document.getElementById('calculate-summary-btn'); 
    const summaryResultsDiv = document.getElementById('summary-results'); 

    if (!kmFormStart || !kmFormEnd || !kmStateContainer || !fechaKmInput) return;

    // Función auxiliar para calcular el resumen de productividad (LOCAL)
    async function calculateAndDisplayKmSummary(date) {
        if (!summaryResultsDiv) return;
        summaryResultsDiv.innerHTML = '<p>Calculando...</p>';
        if (summaryBtn) summaryBtn.disabled = true;

        try {
            const response = await fetch(`/api/summary?date=${date}`, {credentials: 'include'});
            const summary = await response.json();

            if (response.status !== 200) {
                summaryResultsDiv.innerHTML = `<div class="message-box error">Error: ${summary.error || 'API Error'}</div>`;
                return;
            }

            let html = `
                <div class="summary-output">
                    <h4>Resultados para ${date}:</h4>
                    <table class="summary-table">
                        <tr><td>KM Recorrido</td><td>${summary.total_km} KM</td></tr>
                        <tr><td>Ganancia Neta</td><td><strong>${formatCurrency(summary.net_income)}</strong></td></tr>
                        <tr><td>Productividad S/KM</td><td><strong>${formatCurrency(summary.productivity_per_km)}/KM</strong></td></tr>
                    </table>
                    ${summary.is_complete ? '' : '<div class="message-box warning mt-3">⚠️ Información incompleta: Asegúrate de registrar viajes y finalizar el KM.</div>'}
                </div>
            `;
            summaryResultsDiv.innerHTML = html;

        } catch (error) {
            console.error('Error al calcular el resumen en KM:', error);
            summaryResultsDiv.innerHTML = '<div class="message-box error">Error de conexión.</div>';
        } finally {
            if (summaryBtn) summaryBtn.disabled = false;
        }
    }

    // Función de renderizado (GET) - LOCAL
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
            
            // Llama al resumen DEPSUÉS de cargar el estado del KM
            calculateAndDisplayKmSummary(date); 

        } catch (error) {
            console.error('Error al cargar KM:', error);
            kmStateContainer.innerHTML = '<div class="alert alert-danger">Error de conexión al servidor de Kilometraje.</div>';
        }
    }
    
    // ** Listener del cambio de fecha (LOCAL) **
    fechaKmInput.addEventListener('change', (e) => {
        fetchAndDisplayKM(e.target.value);
    });
    
    // Carga inicial
    fetchAndDisplayKM(fechaKmInput.value);


    // Si el botón de resumen existe, lo adjuntamos a la carga inicial de KM
    if (summaryBtn) {
        summaryBtn.addEventListener('click', () => calculateAndDisplayKmSummary(fechaKmInput.value));
    }


    // Manejar el envío de formularios (POST)
    const handleKmSubmit = async (e, action) => {
        e.preventDefault();
        
        const form = e.target;
        const kmValue = form.querySelector('input[name="km_value"]').value;
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
// LÓGICA DE PRESUPUESTO
// =========================================================

function initializeBudgetPage() {
    const PRESUPUESTO_API_URL = '/api/presupuesto';
    // 1. Elementos principales
    const budgetForm = document.getElementById('add-presupuesto-form'); 
    const budgetListContainer = document.getElementById('presupuesto-table'); 
    const budgetMessageDiv = document.getElementById('budget-message'); 

    if (!budgetForm || !budgetListContainer || !budgetMessageDiv) {
        return; 
    }
    
    // 2. Elementos condicionales
    const fijoRadio = document.getElementById('gasto_fijo');
    const variableRadio = document.getElementById('gasto_variable');
    const fechaContainer = document.getElementById('fecha-pago-container');
    const fechaInput = document.getElementById('fecha_pago');
    
    let toggleFechaInput = null; 

    // Configuración condicional de fecha (solo si existen)
    if (fijoRadio && variableRadio && fechaContainer && fechaInput) { 
        
        toggleFechaInput = function() {
            if (fijoRadio.checked) {
                fechaContainer.style.display = 'block';
                fechaInput.setAttribute('required', 'required'); 
            } else {
                fechaContainer.style.display = 'none';
                fechaInput.removeAttribute('required'); 
            }
        };
        
        fijoRadio.addEventListener('change', toggleFechaInput);
        variableRadio.addEventListener('change', toggleFechaInput);
        toggleFechaInput(); 
    }


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
                                `<button class="mark-paid-btn me-2" data-row-index="${rowIndex}">Marcar</button>`
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


    // 4. Manejo del Formulario (POST: Crear nuevo presupuesto)
    budgetForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        budgetMessageDiv.innerHTML = 'Procesando...';
        budgetMessageDiv.className = '';

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
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data),
                credentials: 'include'
            });

            const result = await response.json();

            if (response.ok && result.status === 'ok') {
                budgetMessageDiv.innerHTML = '✅ ¡Presupuesto añadido con éxito!';
                budgetMessageDiv.className = 'message-box alert alert-success';
                budgetForm.reset(); 
                if (fijoRadio) fijoRadio.checked = true;
                if (toggleFechaInput) toggleFechaInput(); 
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

    // 5. Asignar Event Listeners para PUT (Marcar Pagado) y DELETE (Eliminar)
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
                        headers: {'Content-Type': 'application/json'},
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
                        headers: {'Content-Type': 'application/json'},
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
                headers: {'Content-Type': 'application/json'},
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


// =========================================================
// LÓGICA DE RESUMEN DIARIO (SUMMARY PAGE) - AUTÓNOMA (CORREGIDO)
// =========================================================

function initializeSummaryPage() {
    const fechaInput = document.getElementById('summary_fecha');
    const resultsDiv = document.getElementById('summary-results');
    
    if (!fechaInput || !resultsDiv) return;

    // Función para obtener y mostrar el resumen - LOCAL
    async function fetchAndDisplaySummary(date) {
        resultsDiv.innerHTML = '<p>Calculando resumen...</p>';

        try {
            const response = await fetch(`/api/summary?date=${date}`, {credentials: 'include'});
            const summary = await response.json();

            if (response.status !== 200) {
                resultsDiv.innerHTML = `<div class="message-box error">Error al cargar resumen: ${summary.error || 'API Error'}</div>`;
                return;
            }

            // Renderizado de la tabla con la clase summary-table
            let html = `
                <table class="summary-table">
                    <thead>
                        <tr><th>Métrica</th><th>Valor</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Viajes Totales</td><td>${summary.num_trips}</td></tr>
                        <tr><td>KM Recorrido</td><td>${summary.total_km} KM</td></tr>
                        <tr><td>Ingreso Bruto</td><td>${formatCurrency(summary.total_income)}</td></tr>
                        <tr><td>Gasto Total</td><td>${formatCurrency(summary.total_expenses)}</td></tr>
                        <tr><td>Bono Aplicado</td><td>${formatCurrency(summary.current_bonus)}</td></tr>
                        <tr><td>Ganancia Neta</td><td><strong>${formatCurrency(summary.net_income)}</strong></td></tr>
                        <tr><td>Productividad S/KM</td><td><strong>${formatCurrency(summary.productivity_per_km)}/KM</strong></td></tr>
                    </tbody>
                </table>
                ${summary.is_complete ? '' : '<div class="message-box warning mt-3">⚠️ Información incompleta: Asegúrate de registrar viajes y KM final.</div>'}
            `;
            
            resultsDiv.innerHTML = html;

        } catch (error) {
            console.error('Error al cargar el resumen:', error);
            resultsDiv.innerHTML = '<div class="message-box error">Error de conexión al generar el resumen.</div>';
        }
    }
    
    // ** Listener del cambio de fecha (LOCAL) **
    fechaInput.addEventListener('change', (e) => {
        fetchAndDisplaySummary(e.target.value);
    });

    // Carga inicial al iniciar la página
    fetchAndDisplaySummary(fechaInput.value);
}


// =========================================================
// LÓGICA DE REPORTE MENSUAL (REPORTS PAGE)
// =========================================================

function initializeReportPage() {
    const reportForm = document.getElementById('reportForm');
    const reportResultsDiv = document.getElementById('report-results');
    
    // Esta función se llama si reportForm existe (solo en monthly_report.html)
    if (!reportForm || !reportResultsDiv) return;

    reportForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const month = document.getElementById('month').value;
        const year = document.getElementById('year').value;
        
        reportResultsDiv.innerHTML = '<p>Calculando el reporte mensual...</p>';
        document.querySelector('button[type="submit"]').disabled = true;

        try {
            // Llama a la API con los parámetros del formulario
            const response = await fetch(`/api/monthly_report?month=${month}&year=${year}`, {credentials: 'include'});
            const data = await response.json();

            if (response.status !== 200) {
                reportResultsDiv.innerHTML = `<div class="message-box error">Error: ${data.message || data.error || 'API Error'}</div>`;
                return;
            }
            
            const report = data.report;
            
            // Renderizado de la tabla con los estilos summary-table
            let html = `
                <table class="summary-table">
                    <thead>
                        <tr><th>Métrica</th><th>Valor</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Mes / Año</td><td>${report.month} / ${report.year}</td></tr>
                        <tr><td>KM Recorridos</td><td>${report.total_km.toFixed(0)} KM</td></tr>
                        <tr><td>Viajes Totales</td><td>${report.total_trips}</td></tr>
                        <tr><td>Ingreso Bruto Total</td><td>${formatCurrency(report.total_gross_income)}</td></tr>
                        <tr><td>Bono Total</td><td>${formatCurrency(report.total_bonus)}</td></tr>
                        <tr><td>Gasto Total</td><td>${formatCurrency(report.total_expenses)}</td></tr>
                        <tr><td>Ganancia Neta</td><td><strong>${formatCurrency(report.net_income)}</strong></td></tr>
                        <tr><td>Productividad S/KM</td><td><strong>${formatCurrency(report.productivity_per_km)}/KM</strong></td></tr>
                    </tbody>
                </table>
            `;

            reportResultsDiv.innerHTML = html;

        } catch (error) {
            console.error('Error al generar el reporte:', error);
            reportResultsDiv.innerHTML = '<div class="message-box error">Error de conexión al generar el reporte.</div>';
        } finally {
            document.querySelector('button[type="submit"]').disabled = false;
        }
    });
}
