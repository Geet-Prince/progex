// app/static/js/search.js

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('problem-search-input');
    const searchResults = document.getElementById('problem-search-results');
    const selectedProblemsContainer = document.getElementById('selected-problems-container');
    const hiddenProblemsInput = document.getElementById('hidden-problems-input');

    if (!searchInput || !searchResults || !selectedProblemsContainer || !hiddenProblemsInput) {
        // If any of the required elements are missing, do nothing.
        return;
    }

    let selectedProblems = [];
    let debounceTimer;

    // Function to update the hidden input and the display of selected problems
    function updateSelectedProblems() {
        selectedProblemsContainer.innerHTML = '';
        selectedProblems.forEach(problem => {
            const problemTag = document.createElement('div');
            problemTag.className = 'flex items-center bg-primary-green text-dark-bg text-sm font-bold pl-3 pr-2 py-1';
            problemTag.innerHTML = `
                <span>${problem.title}</span>
                <button type="button" class="ml-2 font-mono text-lg leading-none hover:text-accent-red">×</button>
            `;
            // Add event listener to the remove button
            problemTag.querySelector('button').addEventListener('click', () => {
                selectedProblems = selectedProblems.filter(p => p.titleSlug !== problem.titleSlug);
                updateSelectedProblems();
            });
            selectedProblemsContainer.appendChild(problemTag);
        });
        // Update the actual form input that gets submitted
        hiddenProblemsInput.value = selectedProblems.map(p => p.titleSlug).join(',');
    }

    // Function to handle fetching and displaying search results
    async function handleSearch(query) {
        if (query.length < 2) {
            searchResults.innerHTML = '';
            searchResults.classList.add('hidden');
            return;
        }

        try {
            const response = await fetch(`/challenges/search-problems?q=${encodeURIComponent(query)}`);
            if (!response.ok) return;
            const problems = await response.json();

            searchResults.innerHTML = '';
            if (problems.length > 0) {
                searchResults.classList.remove('hidden');
                problems.forEach(problem => {
                    const resultItem = document.createElement('div');
                    resultItem.className = 'px-4 py-2 hover:bg-primary-green hover:text-dark-bg cursor-pointer';
                    resultItem.textContent = problem.title;
                    // Add event listener to add the problem when clicked
                    resultItem.addEventListener('click', () => {
                        if (!selectedProblems.find(p => p.titleSlug === problem.titleSlug)) {
                            selectedProblems.push(problem);
                            updateSelectedProblems();
                        }
                        searchInput.value = '';
                        searchResults.classList.add('hidden');
                        searchInput.focus();
                    });
                    searchResults.appendChild(resultItem);
                });
            } else {
                searchResults.classList.add('hidden');
            }
        } catch (error) {
            console.error('Search failed:', error);
            searchResults.classList.add('hidden');
        }
    }

    // Listen for typing, with a debounce to prevent too many API calls
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            handleSearch(e.target.value);
        }, 250); // Wait 250ms after user stops typing
    });
});
