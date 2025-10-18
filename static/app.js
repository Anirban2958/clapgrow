// ============================================================================
// FOLLOWUP BOSS - Frontend JavaScript
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
    // Store the ID of the follow-up being edited or deleted
    let currentFollowupId = null;

    // ========================================================================
    // MODAL FUNCTIONS
    // ========================================================================
    
    // Open a modal by ID
    window.openModal = (modalId) => {
        document.getElementById(modalId).style.display = "block";
    };

    // Close a modal by ID
    window.closeModal = (modalId) => {
        document.getElementById(modalId).style.display = "none";
    };

    // ========================================================================
    // EDIT FUNCTIONALITY
    // ========================================================================
    
    // Load follow-up data and open edit modal
    // Load follow-up data and open edit modal
    window.editFollowup = async (id) => {
        currentFollowupId = id;
        
        try {
            // Fetch follow-up details from API
            const response = await fetch(`/api/followups/${id}`);
            if (!response.ok) {
                throw new Error('Failed to fetch followup data');
            }
            
            const result = await response.json();
            const followup = result.data;
            
            // Populate edit form with current values
            document.getElementById('editId').value = followup.id;
            document.getElementById('editSource').value = followup.source;
            document.getElementById('editContact').value = followup.contact;
            document.getElementById('editDescription').value = followup.description;
            document.getElementById('editDueDate').value = followup.due_date;
            document.getElementById('editPriority').value = followup.priority;
            document.getElementById('editNotifyEmail').value = followup.notify_email || '';
            
            openModal('editModal');
        } catch (error) {
            console.error('Error loading followup:', error);
            alert('Error loading followup data: ' + error.message);
        }
    };

    // ========================================================================
    // DELETE FUNCTIONALITY
    // ========================================================================
    
    // Load follow-up data and open delete confirmation modal
    // Load follow-up data and open delete confirmation modal
    window.deleteFollowup = async (id) => {
        currentFollowupId = id;
        
        try {
            // Fetch follow-up details to show in confirmation
            const response = await fetch(`/api/followups/${id}`);
            if (!response.ok) {
                throw new Error('Failed to fetch followup data');
            }
            
            const result = await response.json();
            const followup = result.data;
            
            // Show details in confirmation modal
            document.getElementById('deleteContact').textContent = followup.contact;
            document.getElementById('deleteDescription').textContent = followup.description;
            
            openModal('deleteModal');
        } catch (error) {
            console.error('Error loading followup:', error);
            alert('Error loading followup data: ' + error.message);
        }
    };

    // ========================================================================
    // FORM SUBMISSION HANDLERS
    // ========================================================================
    
    // Handle edit form submission (PATCH request)
    // Handle edit form submission (PATCH request)
    document.getElementById('editForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Collect form data
        const formData = {
            source: document.getElementById('editSource').value,
            contact: document.getElementById('editContact').value,
            description: document.getElementById('editDescription').value,
            due_date: document.getElementById('editDueDate').value,
            priority: document.getElementById('editPriority').value,
            notify_email: document.getElementById('editNotifyEmail').value
        };

        try {
            // Send PATCH request to update follow-up
            const response = await fetch(`/api/followups/${currentFollowupId}`, {
                method: 'PATCH',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server response:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Failed to update followup');
            }
            
            // Close modal and reload page
            closeModal('editModal');
            window.location.reload();
        } catch (error) {
            console.error('Error updating followup:', error);
            alert('Error updating followup: ' + error.message);
        }
    });

    // Handle delete confirmation button click (DELETE request)
    // Handle delete confirmation button click (DELETE request)
    document.getElementById('confirmDelete').addEventListener('click', async () => {
        try {
            // Send DELETE request
            const response = await fetch(`/api/followups/${currentFollowupId}`, {
                method: 'DELETE',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server response:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error || 'Failed to delete followup');
            }
            
            // Close modal and reload page
            closeModal('deleteModal');
            window.location.reload();
        } catch (error) {
            console.error('Error deleting followup:', error);
            alert('Error deleting followup: ' + error.message);
        }
    });

    // ========================================================================
    // MODAL BACKDROP CLICK HANDLER
    // ========================================================================
    
    // Close modal when clicking outside of it
    window.addEventListener('click', (event) => {
        if (event.target.classList.contains('modal')) {
            event.target.style.display = 'none';
        }
    });

    // ========================================================================
    // STATUS UPDATE FUNCTIONALITY (Legacy board interactions)
    // ========================================================================
    
    // Animate progress bars based on data attribute
    document.querySelectorAll(".column-progress-bar").forEach((bar) => {
        const value = parseFloat(bar.dataset.progress || "0");
        bar.style.width = `${Math.min(Math.max(value, 0), 100)}%`;
    });

    const board = document.querySelector(".board");
    if (!board) {
        return;
    }

    // Handle status update buttons (Mark Done, Snooze, Back to Pending)
    // Handle status update buttons (Mark Done, Snooze, Back to Pending)
    board.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-action]");
        if (!button) {
            return;
        }

        if (button.disabled) {
            return;
        }

        const followupId = button.dataset.id;
        const action = button.dataset.action;
        const payload = { status: action };

        // Prompt for snooze date if snoozing
        if (action === "Snoozed") {
            const snoozeDate = prompt("Snooze until (YYYY-MM-DD):");
            if (!snoozeDate) {
                return;
            }
            payload.snoozed_till = snoozeDate;
        }

        // Prompt for new due date if moving back to Pending
        if (action === "Pending") {
            const newDue = prompt("Set a new due date (YYYY-MM-DD):");
            if (!newDue) {
                return;
            }
            payload.status = "Pending";
            payload.due_date = newDue;
        }

        try {
            // Send POST request to update status
            const response = await fetch(`/update/${followupId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errorData = await response.json();
                const message = errorData.error || "Unable to update follow-up.";
                alert(message);
                return;
            }

            // Reload page to reflect changes
            window.location.reload();
        } catch (error) {
            alert("Network error updating follow-up. Try again.");
        }
    });
});
