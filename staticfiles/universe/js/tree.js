function toggleNode(button) {
    console.log('Toggle clicked:', button);
    const content = button.parentElement.querySelector('.tree-content');
    console.log('Content element:', content);
    console.log('Current display style:', content.style.display);

    if (content.style.display === 'none' || content.style.display === '') {
        content.style.display = 'block';
        button.textContent = '-';
        console.log('Expanding node');
    } else {
        content.style.display = 'none';
        button.textContent = '+';
        console.log('Collapsing node');
    }
}

// Initialize all tree-content elements to be hidden
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    const contents = document.querySelectorAll('.tree-content');
    console.log('Found tree-content elements:', contents.length);
    contents.forEach(content => {
        content.style.display = 'none';
    });
});