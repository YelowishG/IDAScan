let records = [];

// Fetch records for Class Monitor
async function fetchClassMonitorRecords() {
    try {
        const response = await fetch('/fetch_records');  // Flask endpoint
        if (!response.ok) throw new Error('Network response was not ok');
        records = await response.json();
        if (records.error) throw new Error(records.error);
        console.log('Fetched data:', records);  // Log fetched data
        displayClassMonitorRecords(records);
    } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
    }
}

function displayClassMonitorRecords(data) {
    const tableBody = document.getElementById("recordTable");
    tableBody.innerHTML = "";
    data.forEach(record => {
        console.log('Record:', record);  // Log each record
        const row = `<tr>
                        <td>${record.date}</td>
                        <td>${record.time_in || ''}</td>
                        <td>${record.id_number}</td>
                        <td>${record.name || ''}</td>
                        <td>${record.remarks || ''}</td>
                    </tr>`;
        tableBody.innerHTML += row;
    });
}

function filterClassMonitorRecords() {
    const dateFilter = document.getElementById("dateFilter").value;
    const filteredRecords = records.filter(record => record.date === dateFilter || !dateFilter);
    console.log('Filtered data:', filteredRecords);  // Log filtered data
    displayClassMonitorRecords(filteredRecords);
}

// Fetch records for Student
async function fetchStudentRecords(userId) {
    try {
        const response = await fetch(`/fetch_student_records/${userId}`);  // Flask endpoint
        if (!response.ok) throw new Error('Network response was not ok');
        records = await response.json();
        if (records.error) throw new Error(records.error);
        console.log('Fetched data:', records);  // Log fetched data
        displayStudentRecords(records);
    } catch (error) {
        console.error('There was a problem with the fetch operation:', error);
    }
}

function displayStudentRecords(data) {
    const tableBody = document.getElementById("recordTable");
    tableBody.innerHTML = "";
    data.forEach(record => {
        console.log('Record:', record);  // Log each record
        const row = `<tr>
                        <td>${record.date}</td>
                        <td>${record.time_in || ''}</td>
                        <td>${record.id_number}</td>
                        <td>${record.time_out || ''}</td>
                    </tr>`;
        tableBody.innerHTML += row;
    });

    // Display attendance summary
    const totalAttendances = data.filter(record => record.time_in).length;
    const totalAbsences = data.filter(record => !record.time_in).length;
    const totalSchoolDays = totalAttendances + totalAbsences;
    document.getElementById("totalSchoolDays").textContent = totalSchoolDays;
    document.getElementById("totalAttendances").textContent = totalAttendances;
    document.getElementById("totalAbsences").textContent = totalAbsences;
}

// Initialize functions
window.onload = function() {
    const bodyClass = document.body.classList;
    if (bodyClass.contains('classmonitor')) {
        fetchClassMonitorRecords();
    } else if (bodyClass.contains('student')) {
        const userId = document.body.getAttribute('data-user-id');
        fetchStudentRecords(userId);
    }
};
