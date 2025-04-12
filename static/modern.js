/**
 * US Code Browser - Modern JavaScript
 * Enhances the user experience with interactive features
 */

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all interactive elements
  initSearchBox();
  initTableSorting();
  initCollapsibleSections();
  initActiveNavLinks();
  initScrollToTop();
  initFilterLists();
});

/**
 * Enhances the search box with auto-focus and clear button
 */
function initSearchBox() {
  const searchBox = document.querySelector('.search-box input[type="text"]');
  if (!searchBox) return;
  
  // Auto-focus on search page
  if (window.location.pathname.includes('/search')) {
    searchBox.focus();
  }
  
  // Add clear button
  const clearButton = document.createElement('button');
  clearButton.type = 'button';
  clearButton.className = 'search-clear';
  clearButton.innerHTML = '&times;';
  clearButton.style.display = searchBox.value ? 'block' : 'none';
  
  searchBox.parentNode.insertBefore(clearButton, searchBox.nextSibling);
  
  clearButton.addEventListener('click', function() {
    searchBox.value = '';
    clearButton.style.display = 'none';
    searchBox.focus();
  });
  
  searchBox.addEventListener('input', function() {
    clearButton.style.display = this.value ? 'block' : 'none';
  });
}

/**
 * Makes tables sortable by clicking on column headers
 */
function initTableSorting() {
  const tables = document.querySelectorAll('table.sortable');
  
  tables.forEach(table => {
    const headers = table.querySelectorAll('th');
    
    headers.forEach((header, index) => {
      header.addEventListener('click', function() {
        sortTable(table, index);
      });
      
      // Add sort indicator and cursor style
      header.style.cursor = 'pointer';
      header.innerHTML += ' <span class="sort-indicator">&#8597;</span>';
    });
  });
}

/**
 * Sort table by the specified column index
 */
function sortTable(table, columnIndex) {
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const headers = table.querySelectorAll('th');
  
  // Determine sort direction
  const currentHeader = headers[columnIndex];
  const isAscending = currentHeader.classList.contains('sort-asc');
  
  // Reset all headers
  headers.forEach(header => {
    header.classList.remove('sort-asc', 'sort-desc');
    header.querySelector('.sort-indicator').innerHTML = '&#8597;';
  });
  
  // Set new sort direction
  if (isAscending) {
    currentHeader.classList.add('sort-desc');
    currentHeader.querySelector('.sort-indicator').innerHTML = '&#8595;';
  } else {
    currentHeader.classList.add('sort-asc');
    currentHeader.querySelector('.sort-indicator').innerHTML = '&#8593;';
  }
  
  // Sort the rows
  rows.sort((a, b) => {
    const aValue = a.cells[columnIndex].textContent.trim();
    const bValue = b.cells[columnIndex].textContent.trim();
    
    // Try to sort as numbers if possible
    const aNum = parseFloat(aValue);
    const bNum = parseFloat(bValue);
    
    if (!isNaN(aNum) && !isNaN(bNum)) {
      return isAscending ? bNum - aNum : aNum - bNum;
    }
    
    // Otherwise sort as strings
    return isAscending 
      ? bValue.localeCompare(aValue) 
      : aValue.localeCompare(bValue);
  });
  
  // Reorder the rows
  rows.forEach(row => tbody.appendChild(row));
}

/**
 * Makes sections collapsible for easier navigation
 */
function initCollapsibleSections() {
  const collapsibleHeadings = document.querySelectorAll('.collapsible');
  
  collapsibleHeadings.forEach(heading => {
    // Add toggle indicator
    const indicator = document.createElement('span');
    indicator.className = 'collapse-indicator';
    indicator.innerHTML = '&#9660;'; // Down arrow
    heading.appendChild(indicator);
    
    // Find the content to collapse (next sibling or specified by data attribute)
    const targetSelector = heading.dataset.target;
    const target = targetSelector 
      ? document.querySelector(targetSelector) 
      : heading.nextElementSibling;
    
    if (!target) return;
    
    // Set up click handler
    heading.addEventListener('click', function() {
      const isCollapsed = target.classList.contains('collapsed');
      
      if (isCollapsed) {
        target.classList.remove('collapsed');
        indicator.innerHTML = '&#9660;'; // Down arrow
        target.style.maxHeight = target.scrollHeight + 'px';
      } else {
        target.classList.add('collapsed');
        indicator.innerHTML = '&#9654;'; // Right arrow
        target.style.maxHeight = '0';
      }
    });
    
    // Initialize as expanded
    target.style.overflow = 'hidden';
    target.style.transition = 'max-height 0.3s ease-out';
    target.style.maxHeight = target.scrollHeight + 'px';
  });
}

/**
 * Highlights the active navigation link
 */
function initActiveNavLinks() {
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll('nav a');
  
  navLinks.forEach(link => {
    const linkPath = link.getAttribute('href');
    
    // Check if the current path starts with the link path
    // But make sure it's not just matching the root path for all pages
    if (linkPath !== '/' && currentPath.startsWith(linkPath) || 
        currentPath === linkPath) {
      link.classList.add('active');
    }
  });
}

/**
 * Adds a scroll-to-top button
 */
function initScrollToTop() {
  // Create the button
  const scrollButton = document.createElement('button');
  scrollButton.className = 'scroll-top';
  scrollButton.innerHTML = '&#8593;';
  scrollButton.title = 'Scroll to top';
  document.body.appendChild(scrollButton);
  
  // Show/hide based on scroll position
  window.addEventListener('scroll', function() {
    if (window.pageYOffset > 300) {
      scrollButton.classList.add('visible');
    } else {
      scrollButton.classList.remove('visible');
    }
  });
  
  // Scroll to top when clicked
  scrollButton.addEventListener('click', function() {
    window.scrollTo({
      top: 0,
      behavior: 'smooth'
    });
  });
}

/**
 * Adds filtering capability to lists
 */
function initFilterLists() {
  const filterInputs = document.querySelectorAll('.list-filter');
  
  filterInputs.forEach(input => {
    const targetId = input.dataset.target;
    const target = document.getElementById(targetId);
    
    if (!target) return;
    
    input.addEventListener('input', function() {
      const filterValue = this.value.toLowerCase();
      const items = target.querySelectorAll('li');
      
      items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(filterValue)) {
          item.style.display = '';
        } else {
          item.style.display = 'none';
        }
      });
      
      // Show a message if no results
      let noResultsMsg = target.querySelector('.no-results');
      const hasVisibleItems = Array.from(items).some(item => item.style.display !== 'none');
      
      if (!hasVisibleItems && filterValue) {
        if (!noResultsMsg) {
          noResultsMsg = document.createElement('p');
          noResultsMsg.className = 'no-results';
          noResultsMsg.textContent = 'No matching items found';
          target.appendChild(noResultsMsg);
        }
      } else if (noResultsMsg) {
        noResultsMsg.remove();
      }
    });
  });
}
