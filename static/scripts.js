// =========================================================
// LÓGICA DE PRESUPUESTO
// =========================================================

function initializeBudgetPage() {
    // Usamos la URL relativa ya que el script está en el mismo dominio.
    const PRESUPUESTO_API_URL = '/api/presupuesto'; 
    const budgetForm = document.getElementById('add-presupuesto-form'); // Asegúrate de que el ID del form es 'add-presupuesto-form'
    const budgetListContainer = document.getElementById('presupuesto-table'); // Apuntamos a la tabla completa o al contenedor
    const budgetMessageDiv = document.getElementById('budget-message') || document.createElement('div'); // Mensaje de feedback

    if (document.getElementById('budget-list-container')) {
        // Si el contenedor original está en el HTML, usaremos ese.
        budgetMessageDiv.id = 'budget-message';
        document.getElementById('budget-list-container').prepend(budgetMessageDiv);
    }
    
    // Función para Cargar y Renderizar Presupuestos (GET)
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
                    const rowIndex = i + 2; // Fila en Google Sheets (1-based, +1 por cabecera)
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

    // Manejo del Formulario (POST: Crear nuevo presupuesto)
    if (budgetForm) {
        budgetForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            budgetMessageDiv.innerHTML = 'Procesando...';
            budgetMessageDiv.className = '';

            const tipoGasto = document.querySelector('input[name="tipo_gasto"]:checked').value;
            let fechaPago = '';

            // Lógica de validación de Gasto Fijo
            if (tipoGasto === 'Fijo') {
                const fechaInput = document.getElementById('fecha_pago');
                fechaPago = fechaInput.value;
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
                    // Asegurar que la fecha se muestre/oculte correctamente después del reset
                    if(document.getElementById('fecha-pago-container')) {
                         document.getElementById('fecha-pago-container').style.display = 'block';
                    }
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
    }

    // 3. Asignar Event Listeners para PUT (Marcar Pagado) y DELETE (Eliminar)
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
                        loadBudgets(); // Recarga la lista
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
                        loadBudgets(); // Recarga la lista
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
// LÓGICA DE RECORDATORIOS HOME (Marcar Pagado - Ahora con DELETE)
// Se reajusta para que use la misma función de la página de presupuesto.
// =========================================================

function initializeHomeReminders() {
    const PRESUPUESTO_API_URL = '/api/presupuesto';
    const paidButtons = document.querySelectorAll('.mark-paid-btn');
    const deleteButtons = document.querySelectorAll('.delete-btn'); // Si hay botones DELETE en Home
    
    // Función centralizada para manejar PUT y DELETE en la Home
    const handleHomeAction = async (event, method) => {
        const target = event.target;
        const row_index = target.dataset.rowIndex;
        const category = target.dataset.category;
        
        if (!row_index) return;
        
        let confirmMsg = '';
        if (method === 'PUT') {
            confirmMsg = `¿Estás seguro de que quieres marcar "${category}" como pagado?`;
        } else if (method === 'DELETE') {
             confirmMsg = `¿Estás seguro de que quieres eliminar el recordatorio de "${category}"?`;
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
                    // Si la acción es exitosa, simplemente ocultamos/actualizamos visualmente
                    listItem.style.opacity = '0.5';
                    listItem.innerHTML = `✅ ${category} ${method === 'PUT' ? 'marcado como pagado' : 'eliminado'}. (Recarga la página)`;
                }
            } else {
                alert(`Error al ${method === 'PUT' ? 'marcar como pagado' : 'eliminar'}: ${data.error || 'Error desconocido'}`);
                target.textContent = method === 'PUT' ? 'Marcar como pagado' : 'Eliminar';
                target.disabled = false;
            }
        } catch (error) {
            console.error('Error en la conexión:', error);
            alert('Error de conexión o servidor al intentar actualizar el pago.');
            target.textContent = method === 'PUT' ? 'Marcar como pagado' : 'Eliminar';
            target.disabled = false;
        }
    };
    
    // Asignar listeners a los botones existentes en la Home
    paidButtons.forEach(button => {
        button.addEventListener('click', (e) => handleHomeAction(e, 'PUT'));
    });
    
    deleteButtons.forEach(button => {
        button.addEventListener('click', (e) => handleHomeAction(e, 'DELETE'));
    });
}
// ... (El resto del script se mantiene igual) ...
