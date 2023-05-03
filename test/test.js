





document.addEventListener('mousemove', function(e) {
	var streak = document.createElement('div');
	streak.classList.add('streak');
	streak.style.top = e.clientY + 'px';
	streak.style.left = e.clientX + 'px';
	document.body.appendChild(streak);


	setTimeout(function() {
		streak.remove();
	}, 1000);
});




