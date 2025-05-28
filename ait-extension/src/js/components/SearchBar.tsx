import React, { useState } from 'react';
import { FiSearch } from 'react-icons/fi';
import '../styles/SearchBar.scss';

interface SearchBarProps {
  onSearch: (query: string, type: 'hybrid' | 'semantic' | 'fulltext' | 'transcripts') => void;
}

const SearchBar: React.FC<SearchBarProps> = ({ onSearch }) => {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'fulltext' | 'transcripts'>('hybrid');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(query, searchType);
  };

  const handleClear = () => {
    setQuery('');
    onSearch('', searchType);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-group">
        <FiSearch className="search-icon" />
        <input
          type="text"
          placeholder="Search videos..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {query && (
          <button 
            type="button" 
            onClick={handleClear}
            className="clear-button"
            title="Clear search"
          >
            ✕
          </button>
        )}
      </div>

      <select 
        value={searchType} 
        onChange={(e) => setSearchType(e.target.value as any)}
        className="search-type-select"
        title="Search Type"
        aria-label="Select search type"
      >
        <option value="hybrid">🔀 Hybrid</option>
        <option value="semantic">🧠 Semantic</option>
        <option value="fulltext">📝 Full-text</option>
        <option value="transcripts">🎙️ Transcripts</option>
      </select>

      <button type="submit" className="search-button">
        Search
      </button>
    </form>
  );
};

export default SearchBar;
