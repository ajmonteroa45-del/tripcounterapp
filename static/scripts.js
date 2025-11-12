/* =========================================================
   scripts.js: Lógica de Interacción con la API de Flask (CONSOLIDADO)
   ========================================================= */

// --- VARIABLES GLOBALES DE CONFIGURACIÓN ---
const PRODUCTION_DOMAIN = 'https://www.tripcounter.online';

// --- Utilidad ---
function formatCurrency(value) {
    return `S/${parseFloat(value).toFixed(2)}`;
}


// =========================================================
// INICIALIZACIÓN GLOBAL
// =========================================================

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Referencias de Elementos Comunes ---
    const fechaInput = document.getElementById('fecha'); 
    
    // Asignar inicializadores a las páginas que existen
    if (document.getElementById('trip-form')) initializeTripsPage();
    if (document.getElementById('expense-form')) initializeExpensesPage();
    if (document.getElementById('budget-form')) initializeBudgetPage();
    if (document.getElementById('km-state-container')) initializeKilometrajePage();
    if (document.getElementById('extra-form')) initializeExtrasPage();
    if (document.getElementById('summary_fecha')) initializeSummaryPage(); // NUEVO: Resumen Diario
    if (document.getElementById('reportForm')) initializeReportPage(); // Reporte Mensual
    
    // HOME: Inicializar recordatorios si existen los botones
    if (document.querySelector('.mark-paid-btn')) initializeHomeReminders(); 

    // Escucha el cambio de fecha (si el input existe en la página)
    if (fechaInput) {
        fechaInput.addEventListener('change', () => {
            if (document.getElementById('trip-form')) fetchAndDisplayTrips(fechaInput.value);
            if (document.getElementById('expense-form')) fetchAndDisplayExpenses(fechaInput.value);
        });
    }
});


// =========================================================
// LÓGICA DE VIAJES (TRIPS) - (Función Original)
// =========================================================

function initializeTripsPage() {
    const tripForm = document.getElementById('trip-form');
    const tripsListDiv = document.getElementById('trips-list');
    
    // Función de renderizado (GET) - Código original
    async function fetchAndDisplayTrips(date) {
        if (tripsListDiv) tripsListDiv.innerHTML = 'Cargando viajes...';
        try {
            const response = await fetch(`/api/trips?date=${date}`, {credentials: 'include'});
            const data = await response.json();
            
            // ... (Lógica de renderizado de tabla y resumen) ...
            if (response.status !== 200) {
                if (tripsListDiv) tripsListDiv.innerHTML = `<div class="message-box error">Error al cargar viajes: ${data.error || 'API Error'}</div>`;
                return;
            }

            const trips = data.trips;
            const bonus = parseFloat(data.bonus || 0); 
            
            let html = '';
            
            if (trips.length > 0) {
                // --- Construcción de la Tabla de Viajes ---
                html += `
                    <p>Total de servicios hoy: <strong>${trips.length}</strong></p>
                    <table class="summary-table">
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
                            <td>${trip.Aeropuerto > 0 ? 'Sí' : 'No'}</td>
                            <td><strong>${formatCurrency(rowTotal)}</strong></td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table>`;

                // --- Mostrar Resumen y Bonos ---
                const totalFinalDia = totalDiaViajes + bonus;

                html += `
                    <hr>
                    <div class="card p-3 mt-3">
                        <h4>Resumen de Ingresos</h4>
                        <p>Monto base: <strong>${formatCurrency(totalMonto)}</strong></p>
                        <p>Propina total: <strong>${formatCurrency(totalPropina)}</strong></p>
                        <p>Subtotal: <strong>${formatCurrency(totalDiaViajes)}</strong></p>
                        <h4>💰 Bono: <strong class="text-success">${formatCurrency(bonus)}</strong></h4>
                        <hr>
                        <p class="h4">Total de Ingresos del Día: <strong class="text-primary">${formatCurrency(totalFinalDia)}</strong></p>
                    </div>
                `;

            } else {
                html = '<div class="message-box warning">Aún no hay viajes registrados para este día.</div>';
            }
            
            if (tripsListDiv) tripsListDiv.innerHTML = html;


        } catch (error) {
            console.error('Error al cargar los viajes:', error);
            if (tripsListDiv) tripsListDiv.innerHTML = '<div class="message-box error">Error al conectar con la API de viajes.</div>';
        }
    }

    // Manejar el envío del formulario (POST) - Código original
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
                
                // Limpiar el formulario
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

// ... (El resto de funciones de inicialización siguen un patrón similar) ...


// =========================================================
// LÓGICA DE PRESUPUESTO (Funciones Consolidadas)
// =========================================================

function initializeBudgetPage() {
    const PRESUPUESTO_API_URL = `${PRODUCTION_DOMAIN}/api/presupuesto`;
    const budgetForm = document.getElementById('budget-form');
    const budgetListContainer = document.getElementById('budget-list-container');
    const budgetMessageDiv = document.getElementById('budget-message');

    loadBudgets(); // Carga inicial

    // 2. Manejo del Formulario (POST: Crear nuevo presupuesto)
    budgetForm.addEventListener('submit', async function(event) {
        event.preventDefault();
        budgetMessageDiv.innerHTML = 'Procesando...';
        budgetMessageDiv.className = '';

        const formData = new FormData(budgetForm);
        const data = Object.fromEntries(formData.entries());
        
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
                budgetMessageDiv.className = 'message-box success';
                budgetForm.reset(); 
                loadBudgets(); 
            } else {
                const msg = result.message || result.error || 'Error al añadir presupuesto.';
                budgetMessageDiv.innerHTML = `❌ Error: ${msg}`;
                budgetMessageDiv.className = 'message-box error';
            }
        } catch (error) {
            console.error('Error al enviar el formulario:', error);
            budgetMessageDiv.innerHTML = '❌ Error de conexión con el servidor.';
            budgetMessageDiv.className = 'message-box error';
        }
    });

    // 3. Función para Cargar y Renderizar Presupuestos (GET)
    async function loadBudgets() {
        budgetListContainer.innerHTML = '<p>Cargando presupuestos...</p>';

        try {
            const response = await fetch(PRESUPUESTO_API_URL, { method: 'GET', credentials: 'include'});
            const records = await response.json();

            if (!response.ok) {
                budgetListContainer.innerHTML = `<p class="message-box error">❌ Error al cargar datos: ${records.error || 'No autorizado.'}</p>`;
                return;
            }

            if (records.length === 0) {
                budgetListContainer.innerHTML = '<p>No hay presupuestos registrados.</p>';
                return;
            }

            // 4. Construcción de la Tabla (Similar al código original, pero usando las clases CSS correctas)
            let html = '<table class="summary-table">';
            html += '<thead><tr><th>Categoría</th><th>Monto</th><th>Fecha de Pago</th><th>Pagado</th><th>Acción</th></tr></thead>';
            html += '<tbody>';
            
            records.forEach((r, i) => {
                const rowIndex = i + 2; 
                const isPaid = r.pagado === true || r.pagado === 'True' || r.pagado === 'TRUE';
                
                html += `
                    <tr data-row-index="${rowIndex}" class="${isPaid ? 'paid' : 'pending'}">
                        <td>${r.categoria}</td>
                        <td>${formatCurrency(r.monto)}</td>
                        <td>${r.fecha_pago}</td>
                        <td>${isPaid ? '✅ SÍ' : '❌ NO'}</td>
                        <td>
                            ${isPaid ? 
                                `<span class="message-box success small">Pagado</span>` : 
                                `<button class="btn small mark-paid-btn" data-row-index="${rowIndex}">Marcar como pagado</button>`
                            }
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            budgetListContainer.innerHTML = html;

            // 5. Asignar Event Listeners para la acción PUT
            attachMarkPaidListeners();

        } catch (error) {
            console.error('Error al cargar la lista de presupuestos:', error);
            budgetListContainer.innerHTML = '<p class="message-box error">❌ No se pudo conectar con la API de presupuestos.</p>';
        }
    }
    
    // 6. Función para Marcar como Pagado (PUT)
    function attachMarkPaidListeners() {
        // ... (Tu función PUT original para el listado de presupuestos)
        const markPaidButtons = budgetListContainer.querySelectorAll('.mark-paid-btn');
        
        markPaidButtons.forEach(button => {
            button.addEventListener('click', async (event) => {
                const row_index = event.target.dataset.rowIndex;
                const listItem = event.target.closest('tr');
                const category = listItem.querySelector('td:first-child').textContent;
                
                if (!row_index) return;

                if (!confirm(`¿Marcar "${category}" como pagado?`)) return;

                event.target.disabled = true;
                event.target.textContent = 'Actualizando...';
                
                try {
                    const response = await fetch(PRESUPUESTO_API_URL, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ row_index: row_index }),
                        credentials: 'include'
                    });
                    
                    const result = await response.json();

                    if (response.ok && result.status === 'ok') {
                        loadBudgets(); // Recarga la lista
                    } else {
                        alert(`Error al marcar como pagado: ${result.error || 'Error desconocido'}`);
                        event.target.textContent = 'Marcar como pagado';
                        event.target.disabled = false;
                    }
                } catch (error) {
                    console.error('Error en la conexión:', error);
                    alert('Error de conexión o servidor.');
                    event.target.textContent = 'Marcar como pagado';
                    event.target.disabled = false;
                }
            });
        });
    }
}


// =========================================================
// LÓGICA DE RESUMEN DIARIO (NUEVA LÓGICA)
// =========================================================

function initializeSummaryPage() {
    const SUMMARY_API_URL = `${PRODUCTION_DOMAIN}/api/summary`;
    const dateInput = document.getElementById('summary_fecha');
    const resultsDiv = document.getElementById('summary-results');

    // Carga el resumen inicial (para la fecha predeterminada)
    loadSummary(dateInput.value);

    // Escucha cambios en el input de fecha
    dateInput.addEventListener('change', (event) => {
        loadSummary(event.target.value);
    });

    // Función para obtener datos de la API
    async function loadSummary(targetDate) {
        resultsDiv.innerHTML = '<p>Cargando resumen para ' + targetDate + '...</p>';

        const FETCH_URL = `${SUMMARY_API_URL}?date=${targetDate}`;

        try {
            const response = await fetch(FETCH_URL, {
                method: 'GET',
                credentials: 'include'
            });
            const data = await response.json();

            if (!response.ok || data.error) {
                const msg = data.message || data.error || response.statusText;
                resultsDiv.innerHTML = `<p class="message-box error">❌ Error al cargar el resumen: ${msg}</p>`;
                return;
            }

            // Muestra los resultados
            displaySummary(data);

        } catch (error) {
            console.error('Error al obtener el resumen:', error);
            resultsDiv.innerHTML = '<p class="message-box error">❌ Error de conexión al servidor.</p>';
        }
    }

    // Función para renderizar los resultados en HTML
    function displaySummary(summaryData) {
        if (summaryData.status === 'no_record') {
            resultsDiv.innerHTML = '<p class="message-box warning">⚠️ No hay registro de kilometraje o viajes para esta fecha.</p>';
            return;
        }
        
        const formatProductivity = (value) => `${value.toFixed(2)} S/KM`;
        
        let html = '<section class="card">';
        html += '<h3>Totales del Día</h3>';
        
        html += '<table class="summary-table">';
        html += '<tbody>';
        
        html += `<tr><th>Fecha</th><td>${summaryData.fecha}</td></tr>`;
        html += `<tr><th>Viajes Totales</th><td>${summaryData.num_trips}</td></tr>`;
        html += `<tr><th>Ingreso Total</th><td>${formatCurrency(summaryData.total_income)}</td></tr>`;
        html += `<tr><th>Gasto Total</th><td>${formatCurrency(summaryData.total_expenses)}</td></tr>`;
        html += `<tr><th>Ganancia Neta</th><td>${formatCurrency(summaryData.net_income)}</td></tr>`;
        html += `<tr><th>KM Recorridos</th><td>${summaryData.total_km} KM</td></tr>`;
        html += `<tr><th>Productividad S/KM</th><td>${formatProductivity(summaryData.productivity_per_km)}</td></tr>`;
        
        html += '</tbody></table>';

        if (!summaryData.is_complete) {
             html += '<p class="message-box warning">Nota: Este día aún no está marcado como completo (faltan viajes o KM).</p>';
        }
        
        html += '</section>';
        resultsDiv.innerHTML = html;
    }
}


// =========================================================
// LÓGICA DE RECORDATORIOS HOME (Marcar Pagado)
// =========================================================

function initializeHomeReminders() {
    const PRESUPUESTO_API_URL = `${PRODUCTION_DOMAIN}/api/presupuesto`;
    const paidButtons = document.querySelectorAll('.mark-paid-btn');
    
    paidButtons.forEach(button => {
        // ... (Tu lógica PUT original para la Home)
        button.addEventListener('click', async (event) => {
            const row_index = event.target.dataset.rowIndex;
            const category = event.target.dataset.category;
            
            if (!row_index) return;
            if (!confirm(`¿Estás seguro de que quieres marcar "${category}" (Fila ${row_index}) como pagado?`)) return;

            event.target.disabled = true;
            event.target.textContent = 'Actualizando...';
            
            try {
                const response = await fetch(PRESUPUESTO_API_URL, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ row_index: row_index }),
                    credentials: 'include'
                });
                
                const data = await response.json();

                if (response.ok && data.status === 'ok') {
                    const listItem = event.target.closest('li');
                    if (listItem) {
                        listItem.style.opacity = '0.5';
                        listItem.innerHTML = `✅ ${category} marcado como pagado. (Recarga la página para verificar)`;
                    }
                } else {
                    alert(`Error al marcar como pagado: ${data.error || 'Error desconocido'}`);
                    event.target.textContent = 'Marcar como pagado';
                    event.target.disabled = false;
                }
            } catch (error) {
                console.error('Error en la conexión:', error);
                alert('Error de conexión o servidor al intentar actualizar el pago.');
                event.target.textContent = 'Marcar como pagado';
                event.target.disabled = false;
            }
        });
    });
}


// =========================================================
// LÓGICA DE REPORTE MENSUAL (EXPORT)
// =========================================================

function initializeReportPage() {
    const REPORT_API_URL = `${PRODUCTION_DOMAIN}/api/monthly_report`;
    
    // 1. Obtener Referencias del DOM
    const reportForm = document.getElementById('reportForm');
    const submitButton = document.getElementById('submitButton');
    const monthSelect = document.getElementById('month');
    const yearInput = document.getElementById('year');
    const messageDiv = document.getElementById('message');
    const reportOutputDiv = document.getElementById('reportOutput');

    // ... (El resto de la lógica de Reporte Mensual original) ...
    // Se ha movido aquí para mantener el flujo de trabajo.

    function populateMonths() {
        const months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
        months.forEach((name, index) => {
            const option = document.createElement('option');
            option.value = index + 1; 
            option.textContent = name;
            monthSelect.appendChild(option);
        });
        
        const today = new Date();
        let prevMonth = today.getMonth(); 
        let prevYear = today.getFullYear();

        if (prevMonth === 0) {
            prevMonth = 11;
            prevYear -= 1;
        } else {
            prevMonth -= 1;
        }

        monthSelect.value = prevMonth + 1;
        yearInput.value = prevYear;
    }
    
    reportForm.addEventListener('submit', function(event) {
        event.preventDefault();
        generateReport();
    });
    
    async function generateReport() {
        const month = monthSelect.value;
        const year = yearInput.value;

        messageDiv.innerHTML = '';
        reportOutputDiv.innerHTML = '';
        messageDiv.innerHTML = '⚙️ Solicitando y calculando reporte mensual...';
        messageDiv.className = '';
        submitButton.disabled = true;

        const FETCH_URL = `${REPORT_API_URL}?month=${month}&year=${year}`;

        try {
            const response = await fetch(FETCH_URL, {credentials: 'include'});
            const data = await response.json();

            if (!response.ok || data.error) {
                const errorMessage = data.error 
                    ? `Error de API: ${data.message || data.error}` 
                    : `Error HTTP: ${response.status} - ${response.statusText}`;
                throw new Error(errorMessage);
            }

            displayReportSummary(data.report);
        } catch (error) {
            console.error('Error al generar el reporte:', error);
            messageDiv.innerHTML = `❌ Error: ${error.message}`;
            messageDiv.className = 'message-box error';
        } finally {
            submitButton.disabled = false;
        }
    }

    function displayReportSummary(report) {
        const monthName = monthSelect.options[monthSelect.selectedIndex].text;
        
        messageDiv.innerHTML = `✅ Reporte de **${monthName} de ${report.year}** generado y guardado.`;
        messageDiv.className = 'message-box success';

        let html = `<h3>Resumen de ${monthName}, ${report.year}</h3>`;
        html += `<table class="summary-table">`;
        
        const formatValue = (label, value) => {
            if (typeof value === 'number') {
                if (label.includes('S/') || label.includes('Ganancia')) {
                    return formatCurrency(value);
                }
                if (label.includes('Kilómetros')) {
                    return `${value.toLocaleString('es-PE')} KM`;
                }
                return value.toLocaleString('es-PE');
            }
            return value;
        };

        const fields = [
            ["Ingreso Total (Viajes + Bono)", report.total_gross_income + report.total_bonus],
            ["Bono Total", report.total_bonus],
            ["Gasto Total", report.total_expenses],
            ["Ganancia Neta", report.net_income],
            ["Kilómetros Recorridos", report.total_km],
            ["Viajes Totales", report.total_trips],
            ["Productividad S/KM", report.productivity_per_km],
        ];

        fields.forEach(([label, value]) => {
            html += `<tr><th>${label}</th><td>${formatValue(label, value)}</td></tr>`;
        });

        html += `</table>`;
        
        if (report.save_error) {
             html += `<p class="message-box error" style="margin-top: 15px;">⚠️ Advertencia: Error al guardar el resumen histórico en Google Sheets. Detalle: ${report.save_error}</p>`;
        }

        reportOutputDiv.innerHTML = html;
    }

    populateMonths();
}
