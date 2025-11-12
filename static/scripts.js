8/* =========================================================
   scripts.js: Lógica de Interacción con la API de Flask
   ========================================================= */

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Referencias de Elementos ---
    const fechaInput = document.getElementById('fecha'); // Usado por Viajes y Gastos
    
    // Viajes
    const tripForm = document.getElementById('trip-form');
    const tripsListDiv = document.getElementById('trips-list');
    
    // Gastos
    const expenseForm = document.getElementById('expense-form');
    const expensesListDiv = document.getElementById('expenses-list');
    
    
    // --- Utilidad ---
    function formatCurrency(value) {
        // Asegura que es un número y lo formatea a 2 decimales
        return `S/${parseFloat(value).toFixed(2)}`;
    }
    
    // =========================================================
    // LÓGICA DE VIAJES (TRIPS)
    // =========================================================

    if (tripForm) {
        // Función de renderizado (GET)
        async function fetchAndDisplayTrips(date = fechaInput.value) {
            if (tripsListDiv) {
                tripsListDiv.innerHTML = 'Cargando viajes...';
            }
            // ... (El código de la función fetchAndDisplayTrips que te envié antes va aquí) ...
            try {
                const response = await fetch(`/api/trips?date=${date}`);
                const data = await response.json();
                
                if (response.status !== 200) {
                    if (tripsListDiv) {
                        tripsListDiv.innerHTML = `<div class="alert alert-danger">Error al cargar viajes: ${data.error || 'API Error'}</div>`;
                    }
                    return;
                }

                const trips = data.trips;
                const bonus = parseFloat(data.bonus || 0); 
                
                let html = '';
                
                if (trips.length > 0) {
                    // --- Construcción de la Tabla de Viajes ---
                    html += `
                        <p>Total de servicios hoy: <strong>${trips.length}</strong></p>
                        <div class="table-responsive">
                        <table class="table table-striped table-hover">
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
                    
                    html += `</tbody></table></div>`;

                    // --- Mostrar Resumen y Bonos ---
                    const totalFinalDia = totalDiaViajes + bonus;

                    html += `
                        <hr>
                        <div class="row g-3">
                            <div class="col-md-6">
                                <h4>Resumen de Ingresos por Viajes</h4>
                                <p>Monto base (viajes): <strong>${formatCurrency(totalMonto)}</strong></p>
                                <p>Propina total: <strong>${formatCurrency(totalPropina)}</strong></p>
                                <p>Subtotal (Monto + Propina): <strong>${formatCurrency(totalDiaViajes)}</strong></p>
                            </div>
                            <div class="col-md-6 text-md-end">
                                <h4>💰 Bonificación de Uber</h4>
                                <p class="text-success">Bono por ${trips.length} servicios: <strong>${formatCurrency(bonus)}</strong></p>
                                <hr class="d-md-none">
                                <p class="h4">Total de Ingresos del Día</p>
                                <p class="h2 text-primary"><strong>${formatCurrency(totalFinalDia)}</strong></p>
                            </div>
                        </div>
                    `;

                } else {
                    html = '<div class="alert alert-info">Aún no hay viajes registrados para este día.</div>';
                }
                
                if (tripsListDiv) {
                    tripsListDiv.innerHTML = html;
                }

            } catch (error) {
                console.error('Error al cargar los viajes:', error);
                if (tripsListDiv) {
                    tripsListDiv.innerHTML = '<div class="alert alert-danger">Error al conectar con la API de viajes.</div>';
                }
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
                    body: JSON.stringify(data)
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
        
        fetchAndDisplayTrips(); // Inicializar viajes
    }

    // =========================================================
    // LÓGICA DE GASTOS (EXPENSES)
    // =========================================================
    
    if (expenseForm) {
        // Función de renderizado (GET)
        async function fetchAndDisplayExpenses(date = fechaInput.value) {
            if (expensesListDiv) {
                expensesListDiv.innerHTML = 'Cargando gastos...';
            }
            // ... (El código de la función fetchAndDisplayExpenses que te envié antes va aquí) ...
            try {
                const response = await fetch(`/api/expenses?date=${date}`);
                const expenses = await response.json();
                
                let html = '';
                let totalGastos = 0;
                
                if (expenses.error) {
                    if (expensesListDiv) {
                        expensesListDiv.innerHTML = `<div class="alert alert-danger">Error: ${expenses.error}</div>`;
                    }
                    return;
                }

                if (Array.isArray(expenses) && expenses.length > 0) {
                    // --- Construcción de la Tabla de Gastos ---
                    html += `
                        <p>Total de gastos registrados: <strong>${expenses.length}</strong></p>
                        <div class="table-responsive">
                        <table class="table table-striped table-hover">
                            <thead>
                                <tr><th>Fecha</th><th>Hora</th><th>Monto</th><th>Categoría</th><th>Descripción</th></tr>
                            </thead>
                            <tbody>
                    `;

                    expenses.forEach(exp => {
                        const monto = parseFloat(exp.Monto);
                        totalGastos += monto;
                        
                        html += `
                            <tr>
                                <td>${exp.Fecha}</td>
                                <td>${exp.Hora}</td>
                                <td><strong>${formatCurrency(monto)}</strong></td>
                                <td><span class="badge bg-secondary">${exp.Categoría}</span></td>
                                <td>${exp.Descripción}</td>
                            </tr>
                        `;
                    });
                    
                    html += `</tbody></table></div>`;

                    // --- Resumen de Gastos ---
                    html += `
                        <hr>
                        <h4 class="text-end">Total Gastado en ${date}: 
                            <strong class="text-danger">${formatCurrency(totalGastos)}</strong>
                        </h4>
                    `;

                } else {
                    html = '<div class="alert alert-info">No hay gastos registrados para este día.</div>';
                }
                
                if (expensesListDiv) {
                    expensesListDiv.innerHTML = html;
                }

            } catch (error) {
                console.error('Error al cargar los gastos:', error);
                if (expensesListDiv) {
                    expensesListDiv.innerHTML = '<div class="alert alert-danger">Error al conectar con la API de gastos.</div>';
                }
            }
        }

        // Manejar el envío del formulario (POST)
        expenseForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const data = {
                fecha: expenseForm.fecha.value,
                hora: expenseForm.hora.value,
                monto: expenseForm.monto.value,
                categoria: expenseForm.categoria.value,
                descripcion: expenseForm.descripcion.value
            };
            
            try {
                const response = await fetch('/api/expenses', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                
                if (response.ok) {
                    alert(`Gasto de ${formatCurrency(result.expense.Monto)} registrado con éxito.`);
                    
                    // Limpiar inputs del formulario
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
        
        fetchAndDisplayExpenses(); // Inicializar gastos
    }
    
    // Si la fecha cambia, recarga ambas listas (si están presentes en la misma página)
    if (fechaInput) {
        fechaInput.addEventListener('change', () => {
            if (tripForm) fetchAndDisplayTrips(fechaInput.value);
            if (expenseForm) fetchAndDisplayExpenses(fechaInput.value);
        });
    }
});

// =========================================================
// LÓGICA DE PRESUPUESTO (BUDGET)
// =========================================================

const budgetForm = document.getElementById('budget-form');
const budgetListDiv = document.getElementById('budget-list');

if (budgetForm) {
    
    // Función de renderizado (GET)
    async function fetchAndDisplayBudget() {
        if (budgetListDiv) {
            budgetListDiv.innerHTML = 'Cargando presupuesto...';
        }
        try {
            const response = await fetch('/api/presupuesto');
            const records = await response.json();
            
            if (records.error) {
                if (budgetListDiv) {
                    budgetListDiv.innerHTML = `<div class="alert alert-danger">Error: ${records.error}</div>`;
                }
                return;
            }

            let html = '';
            
            if (records.length > 0) {
                // Filtrar las entradas que corresponden al usuario autenticado (si alias es email)
                // y luego mostrarlas. La API retorna todas, filtramos en el cliente.
                // Usaremos un contador para obtener el row_index (Fila en GSheets)
                let rowCount = 1; // Empezamos en 1 para omitir la cabecera
                
                html += `
                    <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr><th>Categoría</th><th>Monto (USD)</th><th>Fecha de Pago</th><th>Estado</th><th>Acción</th></tr>
                        </thead>
                        <tbody>
                `;

                records.forEach(entry => {
                    rowCount++; // Fila actual en GSheets (usada para la acción PUT)
                    const isPaid = entry.pagado === 'True';
                    
                    html += `
                        <tr class="${isPaid ? 'table-success' : ''}">
                            <td>${entry.categoria}</td>
                            <td>$${parseFloat(entry.monto).toFixed(2)}</td>
                            <td>${entry.fecha_pago}</td>
                            <td>
                                <span class="badge bg-${isPaid ? 'success' : 'warning'}">
                                    ${isPaid ? 'Pagado' : 'Pendiente'}
                                </span>
                            </td>
                            <td>
                                ${!isPaid ? 
                                    `<button data-row-index="${rowCount}" class="btn btn-sm btn-outline-success btn-mark-paid">Marcar Pagado</button>` 
                                    : `<button class="btn btn-sm btn-success" disabled>✔️ Hecho</button>`
                                }
                            </td>
                        </tr>
                    `;
                });
                
                html += `</tbody></table></div>`;

            } else {
                html = '<div class="alert alert-info">Aún no hay categorías de presupuesto añadidas.</div>';
            }
            
            if (budgetListDiv) {
                budgetListDiv.innerHTML = html;
                // Añadir listeners a los botones de "Marcar Pagado" después de renderizar
                document.querySelectorAll('.btn-mark-paid').forEach(button => {
                    button.addEventListener('click', handleMarkPaid);
                });
            }

        } catch (error) {
            console.error('Error al cargar el presupuesto:', error);
            if (budgetListDiv) {
                budgetListDiv.innerHTML = '<div class="alert alert-danger">Error al conectar con la API de presupuesto.</div>';
            }
        }
    }
    
    // Función para manejar el evento PUT (Marcar como pagado)
    async function handleMarkPaid(e) {
        const row_index = e.currentTarget.getAttribute('data-row-index');
        e.currentTarget.disabled = true;
        e.currentTarget.textContent = 'Actualizando...';
        
        try {
            const response = await fetch('/api/presupuesto', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ row_index: row_index })
            });

            if (response.ok) {
                alert('¡Categoría marcada como pagada con éxito!');
                fetchAndDisplayBudget(); // Recargar la lista para mostrar el cambio
            } else {
                const result = await response.json();
                alert(`Error al marcar como pagado: ${result.error || response.statusText}`);
                e.currentTarget.disabled = false;
                e.currentTarget.textContent = 'Marcar Pagado';
            }

        } catch (error) {
            console.error('Error de red al actualizar:', error);
            alert('Error al conectar con el servidor.');
            e.currentTarget.disabled = false;
            e.currentTarget.textContent = 'Marcar Pagado';
        }
    }

    // Manejar el envío del formulario (POST)
    budgetForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            categoria: budgetForm.categoria.value,
            monto: parseFloat(budgetForm.monto_pres.value), // Asegurar que apunta al ID correcto
            fecha_pago: budgetForm.fecha_pago.value
        };
        
        try {
            const response = await fetch('/api/presupuesto', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`Categoría '${result.entry.categoria}' agregada al presupuesto.`);
                
                // Limpiar inputs del formulario
                budgetForm.categoria.value = '';
                budgetForm.monto_pres.value = '';
                
                fetchAndDisplayBudget(); // Recargar la lista
            } else {
                 alert(`Error al agregar presupuesto: ${result.error || response.statusText}`);
            }
            
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    });
    
    fetchAndDisplayBudget(); // Inicializar
}

// =========================================================
// LÓGICA DE KILOMETRAJE
// =========================================================

const kmDateInput = document.getElementById('km_fecha');
const kmContainer = document.getElementById('km-state-container');

if (kmContainer) {
    // Función para renderizar el formulario de inicio o fin
    function renderKilometrajeForm(state, km_inicio = null) {
        let html = '';
        if (state === 'start') {
            html = `
                <h4 class="text-primary">1. Iniciar Jornada</h4>
                <form id="km-form-start" class="mt-3">
                    <label class="form-label">KM Actual (Inicio):
                        <input type="number" name="km_value" class="form-control" required placeholder="Ej: 54321">
                    </label>
                    <label class="form-label mt-2">Notas:
                        <input type="text" name="notas" class="form-control" placeholder="Ej: Full de gasolina">
                    </label>
                    <button type="submit" class="btn btn-primary mt-3">▶️ Iniciar KM</button>
                </form>
            `;
        } else if (state === 'end') {
            html = `
                <h4 class="text-success">2. Finalizar Jornada</h4>
                <div class="alert alert-info">KM de Inicio registrado: <strong>${km_inicio}</strong></div>
                <form id="km-form-end" class="mt-3">
                    <label class="form-label">KM Actual (Fin):
                        <input type="number" name="km_value" class="form-control" required placeholder="Debe ser mayor que ${km_inicio}">
                    </label>
                    <button type="submit" class="btn btn-success mt-3">🏁 Finalizar KM</button>
                </form>
            `;
        } else if (state === 'done') {
            html = `
                <h4 class="text-success">✅ Jornada Finalizada</h4>
                <p>El registro de kilometraje para esta fecha está completo.</p>
                <p>KM Recorrido: <strong>${km_inicio} km</strong></p>
                <div class="alert alert-success mt-3">¡Día productivo! Puedes revisar el resumen.</div>
            `;
        } else {
            html = '<div class="alert alert-warning">Error: Estado desconocido.</div>';
        }
        kmContainer.innerHTML = html;
        attachFormListeners();
    }

    // Función principal para obtener el estado actual
    async function fetchKilometrajeState(date = kmDateInput.value) {
        kmContainer.innerHTML = 'Consultando estado...';
        try {
            const response = await fetch(`/api/kilometraje?date=${date}`);
            const data = await response.json();
            
            if (response.status === 200 && data.status === "no_record") {
                renderKilometrajeForm('start');
            } else if (data.Fecha) {
                const kmInicio = parseInt(data['KM Inicio']);
                const kmFin = data['KM Fin'];
                
                if (kmFin && kmFin !== "") {
                    renderKilometrajeForm('done', data['Recorrido']);
                } else {
                    renderKilometrajeForm('end', kmInicio);
                }
            } else {
                kmContainer.innerHTML = `<div class="alert alert-danger">Error: ${data.message || 'No se pudo cargar el estado.'}</div>`;
            }
        } catch (error) {
            console.error('Error al obtener estado de kilometraje:', error);
            kmContainer.innerHTML = '<div class="alert alert-danger">Error de conexión con la API de kilometraje.</div>';
        }
    }

    // Manejar el envío de los formularios
    function attachFormListeners() {
        // --- Listener de INICIO ---
        const formStart = document.getElementById('km-form-start');
        if (formStart) {
            formStart.addEventListener('submit', async function(e) {
                e.preventDefault();
                const kmValue = formStart.km_value.value;
                const notas = formStart.notas.value;
                
                const response = await sendKmData(kmValue, 'start', notas);
                if (response && response.status === 'start_recorded') {
                    alert(`✅ KM de inicio (${kmValue}) registrado.`);
                    fetchKilometrajeState();
                } else if (response && response.error) {
                    alert(`Error: ${response.message}`);
                }
            });
        }
        
        // --- Listener de FIN ---
        const formEnd = document.getElementById('km-form-end');
        if (formEnd) {
            formEnd.addEventListener('submit', async function(e) {
                e.preventDefault();
                const kmValue = formEnd.km_value.value;
                
                const response = await sendKmData(kmValue, 'end');
                if (response && response.status === 'end_recorded') {
                    alert(`🏁 Jornada finalizada. Recorrido: ${response.recorrido} km.`);
                    fetchKilometrajeState();
                } else if (response && response.error) {
                    alert(`Error: ${response.message}`);
                }
            });
        }
    }
    
    // Función genérica para enviar datos a la API
    async function sendKmData(km_value, action, notas = "") {
        try {
            const response = await fetch('/api/kilometraje', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    date: kmDateInput.value,
                    km_value: km_value,
                    action: action,
                    notas: notas
                })
            });
            return await response.json();
        } catch (error) {
            console.error('Error de red al enviar KM:', error);
            alert('Error de red. Intenta de nuevo.');
            return null;
        }
    }
    
    // Inicialización y cambio de fecha
    fetchKilometrajeState();
    kmDateInput.addEventListener('change', () => fetchKilometrajeState());
}

// =========================================================
// LÓGICA DE RESUMEN DIARIO
// =========================================================

const summaryDateInput = document.getElementById('summary_fecha');
const summaryResultsDiv = document.getElementById('summary-results');

if (summaryResultsDiv) {

    // Función para renderizar los resultados del resumen
    function renderSummary(data) {
        
        const productivityClass = data.productivity_per_km >= 1.0 ? 'text-success' : (data.productivity_per_km > 0 ? 'text-warning' : 'text-danger');
        
        let html = `
            <h4>Resultados para el ${data.fecha}</h4>
            
            <div class="row g-4 mt-3">
                
                <div class="col-md-6">
                    <div class="card p-3 shadow-sm">
                        <h5>💰 Ingresos y Gastos</h5>
                        <hr>
                        <p>Total de Viajes: <strong>${data.num_trips}</strong></p>
                        <p class="h5 text-success">Ingreso Total (Neto + Bono): <strong>${formatCurrency(data.total_income)}</strong></p>
                        <p class="h5 text-danger">Gastos Totales: <strong>${formatCurrency(data.total_expenses)}</strong></p>
                        <hr>
                        <p class="h4">GANANCIA NETA: <strong class="${data.net_income >= 0 ? 'text-success' : 'text-danger'}">${formatCurrency(data.net_income)}</strong></p>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card p-3 shadow-sm">
                        <h5>🚗 Métrica de Productividad</h5>
                        <hr>
                        <p>KM Registrados: <strong>${data.total_km} km</strong></p>
                        <p class="h3 ${productivityClass} mt-3">Soles Netos por KM:</p>
                        <p class="h1 ${productivityClass}">**${data.productivity_per_km.toFixed(2)} S/KM**</p>
                        ${data.productivity_per_km >= 1.0 ? 
                            '<div class="alert alert-success mt-3">¡Excelente Productividad!</div>' : 
                            '<div class="alert alert-warning mt-3">Revisa gastos o busca mayor demanda.</div>'
                        }
                    </div>
                </div>
            </div>
        `;
        
        summaryResultsDiv.innerHTML = html;
    }

    // Función principal para obtener el resumen
    async function fetchDailySummary(date = summaryDateInput.value) {
        summaryResultsDiv.innerHTML = 'Calculando resumen diario...';
        try {
            const response = await fetch(`/api/summary?date=${date}`);
            const data = await response.json();
            
            if (data.error) {
                summaryResultsDiv.innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
                return;
            }
            
            if (data.num_trips === 0 && data.total_km === 0) {
                 summaryResultsDiv.innerHTML = '<div class="alert alert-info">No hay datos de viajes ni kilometraje para esta fecha.</div>';
                 return;
            }
            
            renderSummary(data);

        } catch (error) {
            console.error('Error al obtener resumen:', error);
            summaryResultsDiv.innerHTML = '<div class="alert alert-danger">Error de conexión con la API de resumen.</div>';
        }
    }
    
    // Inicialización y cambio de fecha
    fetchDailySummary();
    summaryDateInput.addEventListener('change', () => fetchDailySummary());
}

// =========================================================
// LÓGICA DE EXTRAS
// =========================================================

const extraForm = document.getElementById('extra-form');
const extrasListDiv = document.getElementById('extras-list');
const fechaExtraInput = document.getElementById('fecha_extra'); // Usamos el ID específico del formulario de extras

if (extraForm) {
    
    // Función de renderizado (GET)
    async function fetchAndDisplayExtras(date = fechaExtraInput.value) {
        if (extrasListDiv) {
            extrasListDiv.innerHTML = 'Cargando extras...';
        }
        try {
            const response = await fetch(`/api/extras?date=${date}`);
            const extras = await response.json();
            
            let html = '';
            let totalExtras = 0;
            
            if (extras.error) {
                if (extrasListDiv) {
                    extrasListDiv.innerHTML = `<div class="alert alert-danger">Error: ${extras.error}</div>`;
                }
                return;
            }

            if (Array.isArray(extras) && extras.length > 0) {
                // --- Construcción de la Tabla de Extras ---
                html += `
                    <p>Total de extras registrados: <strong>${extras.length}</strong></p>
                    <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr><th>#</th><th>Inicio</th><th>Fin</th><th>Monto</th><th>Total</th></tr>
                        </thead>
                        <tbody>
                `;

                extras.forEach(extra => {
                    const monto = parseFloat(extra.Monto);
                    totalExtras += monto;
                    
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
                
                html += `</tbody></table></div>`;

                // --- Resumen de Extras ---
                html += `
                    <hr>
                    <h4 class="text-end">Total de Ingresos Extra: 
                        <strong class="text-primary">${formatCurrency(totalExtras)}</strong>
                    </h4>
                `;

            } else {
                html = '<div class="alert alert-info">No hay viajes extra registrados para este día.</div>';
            }
            
            if (extrasListDiv) {
                extrasListDiv.innerHTML = html;
            }

        } catch (error) {
            console.error('Error al cargar los extras:', error);
            if (extrasListDiv) {
                extrasListDiv.innerHTML = '<div class="alert alert-danger">Error al conectar con la API de extras.</div>';
            }
        }
    }

    // Manejar el envío del formulario (POST)
    extraForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const data = {
            fecha: extraForm.fecha.value,
            hora_inicio: extraForm.hora_inicio.value,
            hora_fin: extraForm.hora_fin.value,
            monto: parseFloat(extraForm.monto.value),
        };
        
        try {
            const response = await fetch('/api/extras', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await response.json();
            
            if (response.ok) {
                alert(`Extra de ${formatCurrency(result.extra.Monto)} registrado con éxito.`);
                
                // Limpiar inputs del formulario
                extraForm.hora_inicio.value = '';
                extraForm.hora_fin.value = '';
                extraForm.monto.value = '';
                
                // Recargar la lista para mostrar el nuevo extra
                fetchAndDisplayExtras(data.fecha);
            } else {
                 alert(`Error al registrar el extra: ${result.error || response.statusText}`);
            }
            
        } catch (error) {
            console.error('Error de red:', error);
            alert('Error al conectar con el servidor.');
        }
    });
    
    // Inicialización y cambio de fecha
    fetchAndDisplayExtras();
    fechaExtraInput.addEventListener('change', () => fetchAndDisplayExtras());
}


// --- LÓGICA ESPECÍFICA PARA EXPORTACIÓN (Añadir al final de script.js) ---

// URL de Producción para la API del reporte
const PRODUCTION_DOMAIN = 'https://www.tripcounter.online'; 
const REPORT_API_URL = `${PRODUCTION_DOMAIN}/api/monthly_report`; 


// Se ejecuta al cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    // ... (Aquí el resto de tu lógica global) ...
    
    // Inicializar la lógica específica del reporte si los elementos existen
    if (document.getElementById('reportForm')) {
        initializeReportPage();
    }
});


function initializeReportPage() {
    // 1. Obtener Referencias del DOM
    const reportForm = document.getElementById('reportForm');
    const submitButton = document.getElementById('submitButton');
    const monthSelect = document.getElementById('month');
    const yearInput = document.getElementById('year');
    const messageDiv = document.getElementById('message');
    const reportOutputDiv = document.getElementById('reportOutput');

    // 2. Rellenar dinámicamente el selector de Meses y Año
    function populateMonths() {
        const months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
        months.forEach((name, index) => {
            const option = document.createElement('option');
            option.value = index + 1; 
            option.textContent = name;
            monthSelect.appendChild(option);
        });
        
        // Establecer el mes anterior por defecto
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
    
    // 3. Manejador de Envío del Formulario
    reportForm.addEventListener('submit', function(event) {
        event.preventDefault();
        generateReport();
    });
    
    // 4. Función Principal de Llamada a la API
    async function generateReport() {
        const month = monthSelect.value;
        const year = yearInput.value;

        // Limpiar mensajes y resultados previos
        messageDiv.innerHTML = '';
        reportOutputDiv.innerHTML = '';
        
        messageDiv.innerHTML = '⚙️ Solicitando y calculando reporte mensual...';
        messageDiv.className = '';
        submitButton.disabled = true;

        const FETCH_URL = `${REPORT_API_URL}?month=${month}&year=${year}`;

        try {
            const response = await fetch(FETCH_URL, {
                // 'include' es clave para enviar las cookies de sesión (autenticación)
                credentials: 'include' 
            });
            const data = await response.json();

            // Manejo de Errores (401, 400, 500, etc.)
            if (!response.ok || data.error) {
                let errorMessage;
                if (response.status === 401) {
                     errorMessage = "No autenticado. Por favor, asegúrate de haber iniciado sesión previamente.";
                } else if (data.error) {
                    errorMessage = `Error de API: ${data.message || data.error}`; 
                } else {
                    errorMessage = `Error HTTP: ${response.status} - ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }

            displayReportSummary(data.report);
            
        } catch (error) {
            console.error('Error al generar el reporte:', error);
            messageDiv.innerHTML = `❌ Error: ${error.message}`;
            messageDiv.className = 'error';
        } finally {
            submitButton.disabled = false;
        }
    }

    // 5. Función para Mostrar el Resultado en la Página
    function displayReportSummary(report) {
        const monthName = monthSelect.options[monthSelect.selectedIndex].text;
        
        messageDiv.innerHTML = `✅ Reporte de **${monthName} de ${report.year}** generado y guardado.`;
        messageDiv.className = 'success';

        let html = `<h3>Resumen de ${monthName}, ${report.year}</h3>`;
        html += `<table class="summary-table">`;
        
        const formatValue = (label, value) => {
            if (typeof value === 'number') {
                if (label.includes('S/') || label.includes('Ganancia')) {
                    return `S/ ${value.toFixed(2)}`;
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
             html += `<p class="error" style="margin-top: 15px;">⚠️ Advertencia: Error al guardar el resumen histórico en Google Sheets. Detalle: ${report.save_error}</p>`;
        }

        reportOutputDiv.innerHTML = html;
    }

    // Ejecutar inicialización
    populateMonths();
}
 

// --- LÓGICA ESPECÍFICA PARA MARCAR PRESUPUESTOS (Añadir a scripts.js) ---

// URL de Producción para la API de presupuesto
const PRODUCTION_DOMAIN = 'https://www.tripcounter.online';
const PRESUPUESTO_API_URL = `${PRODUCTION_DOMAIN}/api/presupuesto`;


document.addEventListener('DOMContentLoaded', () => {
    // ... (Tu lógica global de inicialización) ...
    
    // Inicializar la lógica específica para la página home
    if (document.querySelector('.reminders-section, .card')) {
        initializeHomeReminders();
    }
    // ... (Asegúrate de que tus otras inicializaciones estén aquí) ...
});


function initializeHomeReminders() {
    const paidButtons = document.querySelectorAll('.mark-paid-btn');
    
    paidButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const row_index = event.target.dataset.rowIndex;
            const category = event.target.dataset.category;
            
            if (!row_index) {
                console.error("Índice de fila no encontrado.");
                return;
            }

            // Confirmación opcional para el usuario
            if (!confirm(`¿Estás seguro de que quieres marcar "${category}" (Fila ${row_index}) como pagado?`)) {
                return;
            }

            event.target.disabled = true;
            event.target.textContent = 'Actualizando...';
            
            try {
                const response = await fetch(PRESUPUESTO_API_URL, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    // Enviamos el row_index que la API espera
                    body: JSON.stringify({ row_index: row_index }),
                    credentials: 'include'
                });
                
                const data = await response.json();

                if (response.ok && data.status === 'ok') {
                    // Si es exitoso, actualiza visualmente la lista
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
