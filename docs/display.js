// toggle tabs

function openTab (event, cycleFlag) {
    let tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    
    let tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }

    // Show the current tab, and add an "active" class to the button that opened the tab
    document.getElementById(cycleFlag).style.display = "block";
    event.currentTarget.className += " active";
}

// toggle visibility
function toggleDiv(buttonId, divId, hideText, showText) {
    const div = document.getElementById(divId);
    if (div.style.display === "none") {
        div.style.display = "block";
        document.getElementById(buttonId).innerHTML = hideText;
    } else {
        div.style.display = "none";
        document.getElementById(buttonId).innerHTML = showText;
    }
}
