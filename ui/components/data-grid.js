// ui/components/data-grid.js
import { saveText } from './external.js';
import { toast } from './toast.js';

export class DataGrid {
  constructor(containerElement, config) {
    this.container = containerElement;
    this.columns = config.columns || [];
    this.data = config.data || [];
    this.onRowClick = config.onRowClick || (() => {});
    
    this.sortCol = null;
    this.sortDesc = false;
    this.selectedIds = new Set();
    
    this.render();
  }

  setData(newData) {
    this.data = newData;
    this.selectedIds.clear();
    this.render();
  }

  handleSort(colKey) {
    if (this.sortCol === colKey) {
      this.sortDesc = !this.sortDesc;
    } else {
      this.sortCol = colKey;
      this.sortDesc = false;
    }
    
    this.data.sort((a, b) => {
      let valA = a[colKey] !== undefined && a[colKey] !== null ? a[colKey] : '';
      let valB = b[colKey] !== undefined && b[colKey] !== null ? b[colKey] : '';
      
      if (typeof valA === 'string') valA = valA.toLowerCase();
      if (typeof valB === 'string') valB = valB.toLowerCase();
      
      if (valA < valB) return this.sortDesc ? 1 : -1;
      if (valA > valB) return this.sortDesc ? -1 : 1;
      return 0;
    });
    
    this.render();
  }

  toggleRowSelection(id, e) {
    e.stopPropagation();
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
    } else {
      this.selectedIds.add(id);
    }
    this.renderBulkActionBar();
    
    // Update checkbox state visually without full re-render
    const row = this.container.querySelector(`tr[data-id="${id}"]`);
    if (row) {
      const cb = row.querySelector('input[type="checkbox"]');
      if (cb) cb.checked = this.selectedIds.has(id);
      if (this.selectedIds.has(id)) row.classList.add('selected');
      else row.classList.remove('selected');
    }
  }

  renderBulkActionBar() {
    let bar = this.container.querySelector('.bulk-action-bar');
    if (!bar) {
      bar = document.createElement('div');
      bar.className = 'bulk-action-bar';
      bar.innerHTML = `
        <span class="selection-count">0 selected</span>
        <div class="flex gap-2">
          <button class="btn btn-secondary" id="grid-btn-export">Export Selected</button>
        </div>
      `;
      this.container.appendChild(bar);
      
      const exportBtn = bar.querySelector('#grid-btn-export');
      exportBtn.addEventListener('click', async () => {
        const selectedData = this.data.filter(r => this.selectedIds.has(r.id));
        if (selectedData.length === 0) return;
        
        const headers = this.columns.map(c => c.label).join(',');
        const rows = selectedData.map(row => {
          return this.columns.map(c => {
             let val = row[c.key];
             if (val === null || val === undefined) val = '';
             return '"' + String(val).replace(/"/g, '""') + '"';
          }).join(',');
        });
        // CRLF + a BOM so spreadsheet apps (Excel included) open it cleanly.
        const csv = '\ufeff' + [headers, ...rows].join('\r\n');
        const outcome = await saveText('scrawly-export.csv', csv, 'text/csv');
        if (outcome === 'saved') toast.show(`Exported ${selectedData.length} rows.`, 'success');
        else if (outcome === 'failed') toast.show('Could not save the export. Please try again.', 'error');
      });
    }
    
    bar.querySelector('.selection-count').textContent = `${this.selectedIds.size} selected`;
    
    if (this.selectedIds.size > 0) {
      bar.classList.add('visible');
    } else {
      bar.classList.remove('visible');
    }
  }

  render() {
    this.container.innerHTML = '';
    
    const wrapper = document.createElement('div');
    wrapper.className = 'data-grid-container';
    
    const table = document.createElement('table');
    table.className = 'data-grid stbl';
    
    // Header
    const thead = document.createElement('thead');
    const thr = document.createElement('tr');
    
    // Checkbox column
    const thCb = document.createElement('th');
    thCb.style.width = '40px';
    thCb.innerHTML = `<input type="checkbox" id="grid-select-all">`;
    thr.appendChild(thCb);
    
    this.columns.forEach(col => {
      const th = document.createElement('th');
      th.textContent = col.label;
      if (col.sortable !== false) {
        th.style.cursor = 'pointer';
        if (this.sortCol === col.key) {
          th.textContent += this.sortDesc ? ' ↓' : ' ↑';
        }
        th.addEventListener('click', () => this.handleSort(col.key));
      }
      thr.appendChild(th);
    });
    thead.appendChild(thr);
    table.appendChild(thead);
    
    // Body
    const tbody = document.createElement('tbody');
    this.data.forEach(row => {
      const tr = document.createElement('tr');
      tr.dataset.id = row.id;
      if (this.selectedIds.has(row.id)) tr.classList.add('selected');
      
      // Checkbox
      const tdCb = document.createElement('td');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = this.selectedIds.has(row.id);
      cb.addEventListener('click', (e) => this.toggleRowSelection(row.id, e));
      tdCb.appendChild(cb);
      tr.appendChild(tdCb);
      
      this.columns.forEach(col => {
        const td = document.createElement('td');
        let val = row[col.key];
        
        if (col.render) {
          val = col.render(val, row);
        }
        
        if (val instanceof HTMLElement) {
          td.appendChild(val);
        } else {
          // Plain text only: these values come from crawled pages (titles, meta,
          // headings), so they must never be interpreted as HTML.
          td.textContent = val !== undefined && val !== null ? String(val) : '-';
        }
        
        tr.appendChild(td);
      });
      
      tr.addEventListener('click', () => this.onRowClick(row));
      tbody.appendChild(tr);
    });
    
    table.appendChild(tbody);
    wrapper.appendChild(table);
    this.container.appendChild(wrapper);
    
    // Handle select all logic
    const selectAll = wrapper.querySelector('#grid-select-all');
    if (selectAll) {
      selectAll.checked = this.data.length > 0 && this.selectedIds.size === this.data.length;
      selectAll.addEventListener('change', (e) => {
        if (e.target.checked) {
          this.data.forEach(r => this.selectedIds.add(r.id));
        } else {
          this.selectedIds.clear();
        }
        this.render(); // Re-render all rows to update checkboxes
      });
    }

    this.renderBulkActionBar();
  }
}
