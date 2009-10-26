$(function() {
    var received = {};
    var last_id = 0;
    function receive(data) {
        for ( var i = 0; i < data.length; i++ ) {
            var item = data[i];
            if ( !received[item.id] ) {
                received[item.id] = item.message;
                last_id = Math.max(last_id, item.id);
                var li = $("<li></li>").text(item.message);
                $('#messages').append(li);
            }
        };
        fetch_messages();
    };
    
    function fetch_messages() {
        var url = '/since/';
        if ( last_id ) {
            url += last_id;
        }
        $.ajax({
            success: receive,
            url: url,
            dataType: 'json'
        });
    };
    
    $('form').submit(function(event) {
        event.preventDefault();
        var form = $(this);
        $.ajax({
            url: form.attr('action'),
            type: 'POST',
            data: form.serialize(),
            success: function() {
                form.find(':input[name=message]').val("");
            }
        });
    });
    
    setTimeout(fetch_messages, 1);
});