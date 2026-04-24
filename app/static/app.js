async function moveShift(id, d) {
  if (!id || !d) return;
  const f = new FormData();
  f.append('target_date', d);
  const r = await fetch(`/admin/shifts/move/${id}`, { method: 'POST', body: f });
  if (r.ok) location.reload();
  else alert('Could not move shift');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-shift-id]').forEach(e => {
    e.addEventListener('dragstart', ev => {
      ev.dataTransfer.setData('text/plain', e.dataset.shiftId);
      ev.dataTransfer.effectAllowed = 'move';
    });
  });

  document.querySelectorAll('[data-drop-date]').forEach(z => {
    z.addEventListener('dragover', ev => {
      ev.preventDefault();
      z.classList.add('drop-hover');
    });
    z.addEventListener('dragleave', () => z.classList.remove('drop-hover'));
    z.addEventListener('drop', ev => {
      ev.preventDefault();
      z.classList.remove('drop-hover');
      moveShift(ev.dataTransfer.getData('text/plain'), z.dataset.dropDate);
    });
  });

  document.querySelectorAll('.toggle-edit').forEach(b => b.addEventListener('click', () => {
    const t = document.getElementById(b.dataset.target);
    if (t) t.style.display = t.style.display === 'none' ? 'block' : 'none';
  }));
});
