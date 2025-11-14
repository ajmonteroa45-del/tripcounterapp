/* =========================================================
   scripts.js: Lógica de Interacción con la API de Flask (CONSOLIDADO)
   ========================================================= */

// --- VARIABLES GLOBALES DE CONFIGURACIÓN ---
// Usamos URL relativas si no hay necesidad de un dominio fijo.
// const PRODUCTION_DOMAIN = 'https://www.tripcounter.online'; // Descomentar solo si es necesario

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
    
    // --- CORRECCIÓN CRÍTICA DE PRESUPUESTO ---
    // El formulario de presupuesto tiene el ID 'add-presupuesto-form' en el HTML.
    if (document.getElementById('add-presupuesto-form')) initializeBudgetPage();
    
    if (document.getElementById('km-state-container')) initializeKilometrajePage();
    if (document.getElementById('extra-form')) initializeExtrasPage();
    if (document.getElementById('summary_fecha')) initializeSummaryPage(); 
    if (document.getElementById('reportForm')) initializeReportPage();
    
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


// ... (El resto de initializeTripsPage, initializeExpensesPage, etc. se mantienen igual) ...


// =========================================================
// LÓGICA DE PRESUPUESTO (Funciones Consolidadas)
// =========================================================

function initializeBudgetPage() {
    const PRESUPUESTO_API_URL = '/api/presupuesto';
    // CORRECCIÓN: Usar el ID correcto del formulario
    const budgetForm = document.getElementById('add-presupuesto-form'); 
    // Usaremos la tabla directamente para los listeners de acción
    const budgetListContainer = document.getElementById('presupuesto-table'); 
    // Creamos un div de mensaje si no existe (para feedback POST)
    const budgetMessageDiv = document.getElementById('budget-message') || document.createElement('div'); 

    // Solo cargamos si los elementos principales existen
    if (!budgetForm || !budgetListContainer) return;
    
    // Si el div de mensaje no tiene ID, se lo damos y lo prependemos
    if (!budgetMessageDiv.id) {
        budgetMessageDiv.id = 'budget-message';
        budgetListContainer.closest('.container').prepend(budgetMessageDiv);
    }
    
    // --- Lógica Fijo/Variable (Necesaria para que POST funcione después del reset) ---
    const fijoRadio = document.getElementById('gasto_fijo');
    const variableRadio = document.getElementById('gasto_variable');
    const fechaContainer = document.getElementById('fecha-pago-container');
    const fechaInput = document.getElementById('fecha_pago');
    
    function toggleFechaInput() {
        if (fijoRadio && fijoRadio.checked) {
            fechaContainer.style.display = 'block';
            fechaInput.setAttribute('required', 'required');
        } else if (fechaContainer) {
            fechaContainer.style.display = 'none';
            if (fechaInput) fechaInput.removeAttribute('required');
        }
    }
    
    if (fijoRadio && variableRadio) {
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
                        <td>${r.tipo}</td>
                        <td>${r.fecha_pago || 'N/A'}</td>
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

        const tipoGasto = document.querySelector('input[name="tipo_gasto"]:checked').value;
        let fechaPago = '';

        if (tipoGasto === 'Fijo') {
            fechaPago = document.getElementById('fecha_pago').value;
            if (!fechaPago) {
                budgetMessageDiv.innerHTML = '❌ Error: El gasto fijo requiere una fecha de pago.';
                budgetMessageDiv.className = 'message-box error';
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
                budgetMessageDiv.className = 'message-box success';
                budgetForm.reset(); 
                document.getElementById('gasto_fijo').checked = true; // Reiniciar Fijo/Variable
                toggleFechaInput(); // Aplicar la visibilidad
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


// ... (El resto de initializeHomeReminders, initializeSummaryPage, etc. se mantienen igual) ...

