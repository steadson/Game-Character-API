document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const characterFilter = document.getElementById('character-filter');
    const documentsList = document.getElementById('documents-list');
    const docSearch = document.getElementById('doc-search');
    const searchBtn = document.getElementById('search-btn');
    const uploadDocBtn = document.getElementById('uploadDocBtn');
    const uploadDocModal = document.getElementById('uploadDocModal');
    const viewDocModal = document.getElementById('viewDocModal');
    const documentForm = document.getElementById('documentForm');
    const characterSelect = document.getElementById('character_id');
    
    // Get current user information
    fetchCurrentUser();
    
    // Load characters for filter and form
    loadCharacters();
    
    // Load initial documents
    loadDocuments();
    
    // Event listeners
    uploadDocBtn.addEventListener('click', () => {
        uploadDocModal.style.display = 'block';
    });
    
    // Close modals when clicking on X or outside
    document.querySelectorAll('.close, .cancel-btn').forEach(element => {
        element.addEventListener('click', function() {
            uploadDocModal.style.display = 'none';
            viewDocModal.style.display = 'none';
        });
    });
    
    // Handle document form submission
    documentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        uploadDocument();
    });
    
    // Handle character filter change
    characterFilter.addEventListener('change', function() {
        loadDocuments(characterFilter.value);
    });
    
    // Handle search
    searchBtn.addEventListener('click', function() {
        const searchTerm = docSearch.value.trim();
        if (searchTerm) {
            searchDocuments(searchTerm);
        } else {
            loadDocuments(characterFilter.value);
        }
    });
    
    docSearch.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchBtn.click();
        }
    });
    
    // Functions
    async function fetchCurrentUser() {
        try {
            const response = await fetch('/api/users/me');
            if (response.ok) {
                const userData = await response.json();
                document.getElementById('user-name').textContent = userData.email;
            } else {
                // If not authorized, redirect to login
                window.location.href = '/admin/login';
            }
        } catch (error) {
            console.error('Error fetching user data:', error);
        }
    }
    
    async function loadCharacters() {
        try {
            const response = await fetch('/api/characters/');
            if (response.ok) {
                const characters = await response.json();
                
                // Populate character filter
                characterFilter.innerHTML = '<option value="">All Characters</option>';
                
                // Populate character select in form
                characterSelect.innerHTML = '<option value="">Select Character</option>';
                
                characters.forEach(character => {
                    const filterOption = document.createElement('option');
                    filterOption.value = character.id;
                    filterOption.textContent = character.name;
                    characterFilter.appendChild(filterOption);
                    
                    const selectOption = filterOption.cloneNode(true);
                    characterSelect.appendChild(selectOption);
                });
            }
        } catch (error) {
            console.error('Error loading characters:', error);
        }
    }
    
    async function loadDocuments(characterId = '') {
        try {
            let url = '/api/documents/';
            if (characterId) {
                url += `?character_id=${characterId}`;
            }
            
            const response = await fetch(url);
            if (response.ok) {
                const documents = await response.json();
                renderDocumentsList(documents);
            }
        } catch (error) {
            console.error('Error loading documents:', error);
        }
    }
    
    async function searchDocuments(searchTerm) {
        try {
            let url = `/api/documents/?search=${encodeURIComponent(searchTerm)}`;
            if (characterFilter.value) {
                url += `&character_id=${characterFilter.value}`;
            }
            
            const response = await fetch(url);
            if (response.ok) {
                const documents = await response.json();
                renderDocumentsList(documents);
            }
        } catch (error) {
            console.error('Error searching documents:', error);
        }
    }
    
    function renderDocumentsList(documents) {
        documentsList.innerHTML = '';
        
        if (documents.length === 0) {
            documentsList.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-table">No documents found</td>
                </tr>
            `;
            return;
        }
        
        documents.forEach(doc => {
            const row = document.createElement('tr');
            
            // Format the date
            const createdDate = new Date(doc.created_at);
            const formattedDate = createdDate.toLocaleDateString() + ' ' + 
                                 createdDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            row.innerHTML = `
                <td>${doc.id}</td>
                <td>${doc.title}</td>
                <td>${doc.character_name || 'Unknown'}</td>
                <td>${formatFileType(doc.file_type)}</td>
                <td>${formattedDate}</td>
                <td class="actions">
                    <button class="view-btn" data-id="${doc.id}"><i class="fas fa-eye"></i></button>
                    <button class="delete-btn" data-id="${doc.id}"><i class="fas fa-trash"></i></button>
                </td>
            `;
            
            documentsList.appendChild(row);
        });
        
        // Add event listeners to buttons
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const docId = this.getAttribute('data-id');
                viewDocument(docId);
            });
        });
        
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const docId = this.getAttribute('data-id');
                if (confirm('Are you sure you want to delete this document?')) {
                    deleteDocument(docId);
                }
            });
        });
    }
    
    function formatFileType(fileType) {
        if (!fileType) return 'Unknown';
        
        if (fileType.includes('pdf')) return 'PDF';
        if (fileType.includes('text')) return 'Text';
        if (fileType.includes('word') || fileType.includes('docx')) return 'Word';
        
        return fileType.split('/')[1] || fileType;
    }
    
    async function uploadDocument() {
        const formData = new FormData(documentForm);
        
        try {
            const response = await fetch('/api/documents/', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                uploadDocModal.style.display = 'none';
                documentForm.reset();
                loadDocuments(characterFilter.value);
                showNotification('Document uploaded successfully!', 'success');
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to upload document');
            }
        } catch (error) {
            console.error('Error uploading document:', error);
            showNotification(error.message, 'error');
        }
    }
    
    async function viewDocument(docId) {
        try {
            const response = await fetch(`/api/documents/${docId}`);
            if (response.ok) {
                const doc = await response.json();
                
                // Format the date
                const createdDate = new Date(doc.created_at);
                const formattedDate = createdDate.toLocaleDateString() + ' ' + 
                                     createdDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                document.getElementById('viewDocTitle').textContent = doc.title;
                document.getElementById('docDetails').innerHTML = `
                    <div class="doc-detail-item">
                        <span class="label">ID:</span>
                        <span>${doc.id}</span>
                    </div>
                    <div class="doc-detail-item">
                        <span class="label">Title:</span>
                        <span>${doc.title}</span>
                    </div>
                    <div class="doc-detail-item">
                        <span class="label">Character:</span>
                        <span>${doc.character_name || 'Unknown'}</span>
                    </div>
                    <div class="doc-detail-item">
                        <span class="label">File Type:</span>
                        <span>${formatFileType(doc.file_type)}</span>
                    </div>
                    <div class="doc-detail-item">
                        <span class="label">Created:</span>
                        <span>${formattedDate}</span>
                    </div>
                    <div class="doc-detail-item">
                        <span class="label">Download:</span>
                        <a href="/api/documents/${doc.id}/download" class="download-link" target="_blank">
                            <i class="fas fa-download"></i> Download File
                        </a>
                    </div>
                `;
                
                viewDocModal.style.display = 'block';
            } else {
                throw new Error('Failed to fetch document details');
            }
        } catch (error) {
            console.error('Error viewing document:', error);
            showNotification(error.message, 'error');
        }
    }
    
    async function deleteDocument(docId) {
        try {
            const response = await fetch(`/api/documents/${docId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                loadDocuments(characterFilter.value);
                showNotification('Document deleted successfully!', 'success');
            } else {
                throw new Error('Failed to delete document');
            }
        } catch (error) {
            console.error('Error deleting document:', error);
            showNotification(error.message, 'error');
        }
    }
    
    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span>${message}</span>
            <button class="close-notification">&times;</button>
        `;
        
        // Add to DOM
        document.body.appendChild(notification);
        
        // Add event listener to close button
        notification.querySelector('.close-notification').addEventListener('click', function() {
            notification.remove();
        });
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
});