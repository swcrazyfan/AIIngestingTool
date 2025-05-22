import React, { useState } from 'react';
import { ingestApi } from '../api/client';
import { IngestProgress } from '../types/api';
import { evalTS } from '../lib/utils/bolt';
import { FiFolder, FiPlay, FiCheckSquare, FiSquare } from 'react-icons/fi';
import '../styles/IngestPanel.scss';

const IngestPanel: React.FC = () => {
  const [selectedDirectory, setSelectedDirectory] = useState('');
  const [ingestOptions, setIngestOptions] = useState({
    recursive: true,
    ai_analysis: false,
    generate_embeddings: false,
    store_database: false
  });
  const [progress, setProgress] = useState<IngestProgress | null>(null);
  const [isIngesting, setIsIngesting] = useState(false);

  const selectDirectory = async () => {
    try {
      const directory = await evalTS("selectDirectory");
      if (directory) {
        setSelectedDirectory(directory);
      }
    } catch (error) {
      console.error('Failed to select directory:', error);
    }
  };

  const startIngest = async () => {
    if (!selectedDirectory) return;

    setIsIngesting(true);
    setProgress({ status: 'running', progress: 0, message: 'Starting ingest...' });

    try {
      await ingestApi.startIngest(selectedDirectory, ingestOptions);
      
      // Poll for progress
      const pollInterval = setInterval(async () => {
        const progressData = await ingestApi.getProgress();
        setProgress(progressData);
        
        if (progressData.status === 'completed' || progressData.status === 'failed') {
          clearInterval(pollInterval);
          setIsIngesting(false);
        }
      }, 1000);
    } catch (error) {
      console.error('Ingest failed:', error);
      setProgress({ status: 'failed', progress: 0, message: 'Ingest failed' });
      setIsIngesting(false);
    }
  };
  const toggleOption = (option: keyof typeof ingestOptions) => {
    setIngestOptions(prev => ({
      ...prev,
      [option]: !prev[option]
    }));
  };

  return (
    <div className="ingest-panel">
      <h2>Process Videos</h2>

      <div className="directory-selection">
        <button onClick={selectDirectory} className="select-directory-btn">
          <FiFolder /> Select Directory
        </button>
        
        {selectedDirectory && (
          <div className="selected-path">{selectedDirectory}</div>
        )}
      </div>

      <div className="ingest-options">
        <h3>Processing Options</h3>
        
        <label className="option-item">
          <button onClick={() => toggleOption('recursive')} className="checkbox">
            {ingestOptions.recursive ? <FiCheckSquare /> : <FiSquare />}
          </button>
          <div className="option-content">
            <span className="option-label">Recursive Scan</span>
            <span className="option-desc">Include subdirectories</span>
          </div>
        </label>

        <label className="option-item">
          <button onClick={() => toggleOption('ai_analysis')} className="checkbox">
            {ingestOptions.ai_analysis ? <FiCheckSquare /> : <FiSquare />}
          </button>
          <div className="option-content">
            <span className="option-label">AI Analysis</span>
            <span className="option-desc">Comprehensive video analysis</span>
          </div>
        </label>

        <label className="option-item">
          <button onClick={() => toggleOption('generate_embeddings')} className="checkbox">
            {ingestOptions.generate_embeddings ? <FiCheckSquare /> : <FiSquare />}
          </button>
          <div className="option-content">
            <span className="option-label">Generate Embeddings</span>
            <span className="option-desc">Enable semantic search</span>
          </div>
        </label>

        <label className="option-item">
          <button onClick={() => toggleOption('store_database')} className="checkbox">
            {ingestOptions.store_database ? <FiCheckSquare /> : <FiSquare />}
          </button>
          <div className="option-content">
            <span className="option-label">Store in Database</span>
            <span className="option-desc">Save to Supabase</span>
          </div>
        </label>
      </div>

      <button 
        onClick={startIngest} 
        className="start-ingest-btn"
        disabled={!selectedDirectory || isIngesting}
      >
        <FiPlay /> Start Processing
      </button>

      {progress && (
        <div className="progress-section">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress.progress}%` }}
            />
          </div>
          <div className="progress-info">
            <span className="progress-message">{progress.message}</span>
            <span className="progress-percent">{Math.round(progress.progress)}%</span>
          </div>
          {progress.results_count !== undefined && (
            <div className="progress-stats">
              Processed: {progress.results_count} videos
              {progress.failed_count !== undefined && progress.failed_count > 0 && ` (${progress.failed_count} failed)`}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default IngestPanel;
