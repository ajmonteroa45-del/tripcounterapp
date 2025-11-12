/* =========================================================
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
