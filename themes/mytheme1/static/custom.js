// compress and expand details tags with a neat arrow
var classname = "details-show";
$("details").each(function(i) {
    var di = document.createElement("span");
    di.id = "details-icon";
    if ($(this).prop("open")) {
        di.innerHTML = "&#x25BC;";
        di.className = classname;
    } else {
        di.innerHTML = "&#x25BA;";
    }
    $(this).find("summary").first().prepend("&nbsp;").prepend(di);
    $("<hr/>").insertBefore(this);
    $("<hr/>").insertAfter(this);
});

$("summary").on('click', function(e) {
    var di = $(this).find("#details-icon").first();
    if (di.hasClass(classname)) {
        di.html("&#x25BA;");
        di.removeClass(classname);
    } else {
        di.html("&#x25BC;");
        di.addClass(classname);
    }
});

// https://stackoverflow.com/a/43321596
$("summary").mousedown(function(e) { if (e.detail > 1) { e.preventDefault(); } });
