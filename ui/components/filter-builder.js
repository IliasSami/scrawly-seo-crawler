// ui/components/filter-builder.js

export class FilterBuilder {
  constructor(containerElement, columns, onFilterChange) {
    this.container = containerElement;
    this.columns = columns; // array of {key, label}
    this.onFilterChange = onFilterChange; // callback with active filters
    
    this.filters = []; // array of {colKey, op, value}
    
    this.render();
  }

  addFilter() {
    this.filters.push({
      colKey: this.columns[0]?.key || '',
      op: 'equals',
      value: ''
    });
    this.render();
    this.triggerChange();
  }

  removeFilter(index) {
    this.filters.splice(index, 1);
    this.render();
    this.triggerChange();
  }

  updateFilter(index, field, value) {
    this.filters[index][field] = value;
    this.triggerChange();
  }

  triggerChange() {
    this.onFilterChange(this.filters);
  }

  render() {
    this.container.innerHTML = '';
    
    const wrapper = document.createElement('div');
    wrapper.className = 'filter-builder';
    
    // Top bar: Search + Add Filter
    const topBar = document.createElement('div');
    topBar.className = 'flex gap-2';
    topBar.style.alignItems = 'center';
    topBar.innerHTML = `
      <input type="text" class="filter-input flex-1" placeholder="Search across all columns..." id="global-search">
      <button class="btn btn-secondary" id="btn-add-filter">+ Add Rule</button>
    `;
    wrapper.appendChild(topBar);
    
    // Filter rows
    const rulesContainer = document.createElement('div');
    rulesContainer.className = 'flex-col gap-2';
    if (this.filters.length > 0) {
      rulesContainer.style.marginTop = 'var(--space-2)';
    }
    
    this.filters.forEach((f, idx) => {
      const row = document.createElement('div');
      row.className = 'filter-row';
      
      // Column Select
      const colSelect = document.createElement('select');
      colSelect.className = 'filter-select';
      this.columns.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.key;
        opt.textContent = c.label;
        if (c.key === f.colKey) opt.selected = true;
        colSelect.appendChild(opt);
      });
      colSelect.addEventListener('change', e => this.updateFilter(idx, 'colKey', e.target.value));
      
      // Operator Select
      const opSelect = document.createElement('select');
      opSelect.className = 'filter-select';
      const ops = ['equals', 'contains', 'starts with', 'greater than', 'less than'];
      ops.forEach(op => {
        const opt = document.createElement('option');
        opt.value = op;
        opt.textContent = op;
        if (op === f.op) opt.selected = true;
        opSelect.appendChild(opt);
      });
      opSelect.addEventListener('change', e => this.updateFilter(idx, 'op', e.target.value));
      
      // Value Input
      const valInput = document.createElement('input');
      valInput.type = 'text';
      valInput.className = 'filter-input';
      valInput.value = f.value;
      valInput.addEventListener('input', e => this.updateFilter(idx, 'value', e.target.value));
      
      // Remove btn
      const rmBtn = document.createElement('button');
      rmBtn.className = 'filter-remove';
      rmBtn.innerHTML = '✕';
      rmBtn.title = 'Remove rule';
      rmBtn.addEventListener('click', () => this.removeFilter(idx));
      
      row.appendChild(colSelect);
      row.appendChild(opSelect);
      row.appendChild(valInput);
      row.appendChild(rmBtn);
      
      rulesContainer.appendChild(row);
    });
    
    wrapper.appendChild(rulesContainer);
    this.container.appendChild(wrapper);
    
    // Bind global search
    const globalSearch = wrapper.querySelector('#global-search');
    globalSearch.addEventListener('input', (e) => {
      // we can pass a special flag or just trigger the callback
      this.onFilterChange(this.filters, e.target.value);
    });
    
    wrapper.querySelector('#btn-add-filter').addEventListener('click', () => this.addFilter());
  }
}
