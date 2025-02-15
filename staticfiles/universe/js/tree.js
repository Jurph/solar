function toggleNode(button) {
    if (!button) {
        console.error('Button is null');
        return;
    }

    const parent = button.parentElement;
    if (!parent) {
        console.error('Parent element not found');
        return;
    }

    const content = parent.querySelector('.tree-content');
    if (!content) {
        console.error('Content element not found');
        return;
    }

    // Log the current state
    console.log('Current display:', content.style.display);
    
    // Toggle the display
    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        button.textContent = '-';
    } else {
        content.style.display = 'none';
        button.textContent = '+';
    }
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');
    
    // Find all toggle buttons
    const buttons = document.querySelectorAll('.toggle-btn');
    console.log('Found buttons:', buttons.length);
    
    // Initialize all content as hidden
    const contents = document.querySelectorAll('.tree-content');
    console.log('Found content elements:', contents.length);
    contents.forEach(content => {
        content.style.display = 'none';
    });
});