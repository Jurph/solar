function toggleNode(button) {
    // Toggle button state
    button.classList.toggle('expanded');
    button.textContent = button.classList.contains('expanded') ? '-' : '+';
    
    // Toggle content visibility
    const content = button.parentElement.querySelector('.tree-content');
    content.classList.toggle('expanded');
}