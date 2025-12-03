document.addEventListener('DOMContentLoaded', () => {
    const carousel = document.querySelector('.team-carousel');
    if (!carousel) return;

    const track = carousel.querySelector('.team-carousel__track');
    const slides = Array.from(track.children);
    const nextButton = carousel.querySelector('.carousel-button--next');
    const prevButton = carousel.querySelector('.carousel-button--prev');

    
    const slideWidth = slides[0].getBoundingClientRect().width;
    const slidesToShow = window.innerWidth > 1024 ? 3 : window.innerWidth > 768 ? 2 : 1;

    
    const setSlidePosition = (slide, index) => {
        slide.style.left = `${slideWidth * index}px`;
    };
    slides.forEach(setSlidePosition);

    const moveToSlide = (currentSlide, targetSlide) => {
        const targetIndex = slides.indexOf(targetSlide);
        const moveAmount = targetSlide.style.left;
        track.style.transform = `translateX(-${moveAmount})`;
        currentSlide.classList.remove('current-slide');
        targetSlide.classList.add('current-slide');
    };

    
    const updateButtons = (targetIndex) => {
        prevButton.disabled = targetIndex === 0;
        nextButton.disabled = targetIndex >= slides.length - slidesToShow;

        prevButton.style.opacity = prevButton.disabled ? '0.3' : '1';
        nextButton.style.opacity = nextButton.disabled ? '0.3' : '1';
    };

    
    nextButton.addEventListener('click', () => {
        const currentSlide = track.querySelector('.current-slide');
        const nextSlide = currentSlide.nextElementSibling;
        if (!nextSlide) return;

        moveToSlide(currentSlide, nextSlide);
        updateButtons(slides.indexOf(nextSlide));
    });

    prevButton.addEventListener('click', () => {
        const currentSlide = track.querySelector('.current-slide');
        const prevSlide = currentSlide.previousElementSibling;
        if (!prevSlide) return;

        moveToSlide(currentSlide, prevSlide);
        updateButtons(slides.indexOf(prevSlide));
    });

    
    slides[0].classList.add('current-slide');
    updateButtons(0);

    
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            const currentSlide = track.querySelector('.current-slide');
            const currentIndex = slides.indexOf(currentSlide);

            
            const newSlideWidth = slides[0].getBoundingClientRect().width;
            slides.forEach((slide, index) => {
                slide.style.left = `${newSlideWidth * index}px`;
            });

            
            moveToSlide(currentSlide, slides[currentIndex]);
            updateButtons(currentIndex);
        }, 100);
    });
});
