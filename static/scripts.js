// scripts.js - AJAX handlers for trips/extras/presupuesto
document.addEventListener("DOMContentLoaded", function () {
  // Detect forms and lists
  const tripForm = document.getElementById("trip-form");
  const tripsList = document.getElementById("trips-list");
  const extraForm = document.getElementById("extra-form");
  const extrasList = document.getElementById("extras-list");
  const budgetForm = document.getElementById("budget-form");
  const budgetList = document.getElementById("budget-list");

  // Helper to format money
  function fmt(v){ return Number(v).toFixed(2); }

  // Load today's trips
  async function loadTrips(){
    if(!tripsList) return;
    const d = document.getElementById("fecha") ? document.getElementById("fecha").value : null;
    const res = await fetch(`/api/trips?date=${d || ""}`);
    const data = await res.json();
    if(data.length === 0) {
      tripsList.innerHTML = "<em>No hay viajes registrados para la fecha.</em>";
      return;
    }
    let html = '<table class="trip-table"><thead><tr><th>#</th><th>Inicio</th><th>Fin</th><th>Propina</th><th>Aeropuerto</th><th>Total</th></tr></thead><tbody>';
    data.forEach(r=>{
      html += `<tr>
        <td>${r.Numero}</td>
        <td>${r["Hora inicio"]}</td>
        <td>${r["Hora fin"]}</td>
        <td>${r.Propina || 0}</td>
        <td>${r.Aeropuerto || 0}</td>
        <td>${Number(r.Total).toFixed(2)}</td>
      </tr>`;
    });
    html += "</tbody></table>";
    tripsList.innerHTML = html;
  }

  async function loadExtras(){
    if(!extrasList) return;
    const d = document.getElementById("fecha_extra") ? document.getElementById("fecha_extra").value : null;
    const res = await fetch(`/api/extras?date=${d || ""}`);
    const data = await res.json();
    if(data.length === 0) {
      extrasList.innerHTML = "<em>No hay viajes extra registrados para la fecha.</em>";
      return;
    }
    let html = '<table class="trip-table"><thead><tr><th>#</th><th>Inicio</th><th>Fin</th><th>Monto</th></tr></thead><tbody>';
    data.forEach(r=>{
      html += `<tr>
        <td>${r.Numero}</td>
        <td>${r["Hora inicio"]}</td>
        <td>${r["Hora fin"]}</td>
        <td>${Number(r.Total).toFixed(2)}</td>
      </tr>`;
    });
    html += "</tbody></table>";
    extrasList.innerHTML = html;
  }

  async function loadBudget(){
    if(!budgetList) return;
    const res = await fetch("/api/presupuesto");
    const data = await res.json();
    if(data.length === 0){
      budgetList.innerHTML = "<em>No hay categorías agregadas.</em>";
      return;
    }
    let html = '<ul class="budget-list">';
    data.forEach((r, idx)=>{
      html += `<li>${r.categoria} — $${Number(r.monto).toFixed(2)} — ${r.fecha_pago} — Pagado: ${r.pagado} 
        <button class="btn tiny" onclick="markPaid(${idx+2})">Marcar pagado</button></li>`;
      // NOTE: row index in sheet is idx+2 (header + 1-based)
    });
    html += "</ul>";
    budgetList.innerHTML = html;
  }

  // Expose markPaid globally (simple approach)
  window.markPaid = async function(row_index){
    const res = await fetch("/api/presupuesto", {
      method: "PUT",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({row_index})
    });
    if(res.ok) loadBudget();
    else alert("No se pudo marcar como pagado.");
  };

  // Submit trip
  if(tripForm){
    tripForm.addEventListener("submit", async function(e){
      e.preventDefault();
      const payload = {
        fecha: document.getElementById("fecha").value,
        hora_inicio: document.getElementById("hora_inicio").value,
        hora_fin: document.getElementById("hora_fin").value,
        monto: document.getElementById("monto").value,
        propina: document.getElementById("propina").value || 0,
        aeropuerto: document.getElementById("aeropuerto").checked
      };
      const res = await fetch("/api/trips", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      if(res.status === 201){
        await loadTrips();
        tripForm.reset();
      } else if(res.status === 409){
        alert("Viaje duplicado detectado (misma hora inicio/fin).");
      } else {
        const j = await res.json();
        alert("Error: " + (j.error || "no se pudo guardar"));
      }
    });
    loadTrips();
  }

  if(extraForm){
    extraForm.addEventListener("submit", async function(e){
      e.preventDefault();
      const payload = {
        fecha: document.getElementById("fecha_extra").value,
        hora_inicio: document.getElementById("hora_inicio_extra").value,
        hora_fin: document.getElementById("hora_fin_extra").value,
        monto: document.getElementById("monto_extra").value
      };
      const res = await fetch("/api/extras", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      if(res.status === 201){
        await loadExtras();
        extraForm.reset();
      } else if(res.status === 409){
        alert("Viaje duplicado detectado (misma hora inicio/fin).");
      } else {
        const j = await res.json();
        alert("Error: " + (j.error || "no se pudo guardar"));
      }
    });
    loadExtras();
  }

  if(budgetForm){
    budgetForm.addEventListener("submit", async function(e){
      e.preventDefault();
      const payload = {
        categoria: document.getElementById("categoria").value,
        monto: document.getElementById("monto_pres").value,
        fecha_pago: document.getElementById("fecha_pago").value
      };
      const res = await fetch("/api/presupuesto", {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      if(res.status === 201){
        await loadBudget();
        budgetForm.reset();
      } else {
        alert("Error al crear presupuesto");
      }
    });
    loadBudget();
  }
});