import React, { useState, useEffect } from 'react';
import { ingestApi } from '../api/client';
import { IngestProgress } from '../types/api';
import { evalTS } from '../lib/utils/bolt';
import { FiFolder, FiPlay, FiCheckSquare, FiSquare, FiRefreshCw } from 'react-icons/fi';
import { useWebSocket } from '../contexts/WebSocketContext';
import '../styles/IngestPanel.scss';

const IngestPanel: React.FC = () => {
  const [selectedDirectory, setSelectedDirectory] = useState('');
  const [ingestOptions, setIngestOptions] = useState({
    recursive: true,
    ai_analysis: true,
    generate_embeddings: true,
    store_database: true, // Always true by default, no UI control
    force_reprocess: false
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState<boolean>(false);
  
  // Use the global WebSocket connection
  const { ingestProgress, connected, setIngestProgress } = useWebSocket();

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
    
    setIsLoading(true);
    // Clear previous errors before new attempt
    setError(null); 
    try {
      await ingestApi.startIngest(selectedDirectory, ingestOptions);
      
      // Show progress section
      setShowProgress(true);
      // setError(null); // Already cleared above
    } catch (error: any) { // Catch specific error type if known, else 'any'
      console.error('Ingest failed in IngestPanel:', error);
      // Use the error message from the caught error object
      setError(error.message || 'Failed to start ingest process'); 
    } finally {
      setIsLoading(false);
    }
  };

  const toggleOption = (option: keyof typeof ingestOptions) => {
    setIngestOptions(prev => ({
      ...prev,
      [option]: !prev[option]
    }));
  };

  // Check for ongoing ingest process on load
  useEffect(() => {
    const checkIngestProgress = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // Only make an API call if WebSocket is not connected yet
        if (!connected) {
          const progressData = await ingestApi.getProgress();
          
          // If there's an active ingest process
          if (progressData && (progressData.status === 'running' || 
                              progressData.status === 'scanning' || 
                              progressData.status === 'processing')) {
            setShowProgress(true);
          }
        }
      } catch (error) {
        console.error('Failed to check ingest status:', error);
        setError('Failed to check ingest status');
      } finally {
        setIsLoading(false);
      }
    };
    
    checkIngestProgress();
  }, [connected]);
  
  // Update UI based on ingest progress from WebSocket
  useEffect(() => {
    if (ingestProgress) {
      // Show progress section if there's an active process
      const activeStatuses = ['starting', 'running', 'scanning', 'processing'];
      const completeStatuses = ['idle', 'completed', 'failed'];
      
      if (activeStatuses.includes(ingestProgress.status)) {
        setShowProgress(true);
      }
      
      // Hide progress after a delay when process completes
      if (completeStatuses.includes(ingestProgress.status)) {
        setTimeout(() => {
          setShowProgress(false);
        }, 5000);  // Show completed status for 5 seconds
      }
    }
  }, [ingestProgress]);

  // Poll for progress updates when WebSocket is not connected
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    
    if (!connected && showProgress) {
      // Poll every 2 seconds when WebSocket is not available
      intervalId = setInterval(async () => {
        try {
          const progress = await ingestApi.getProgress();
          // If we got progress data, update UI
          if (progress) {
            setIngestProgress(progress);
          }
        } catch (error) {
          console.error('Failed to poll ingest progress:', error);
        }
      }, 2000);
    }
    
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [connected, showProgress]);

  return (
    <div className="ingest-panel">
      <h2>Video Ingest</h2>
      
      <div className="ingest-panel-content scrollable-content">
        {isLoading ? (
          <div className="loading-state">
            <FiRefreshCw className="loading-icon" />
            <p>Checking ingest status...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <p className="error-message">{error}</p>
            <button onClick={() => {
              setIsLoading(true);
              setError(null);
              // Try to get the latest progress
              ingestApi.getProgress().then(() => {
                setIsLoading(false);
              }).catch(() => {
                setIsLoading(false);
                setError('Failed to connect to server');
              });
            }}>Retry</button>
          </div>
        ) : ingestProgress && (ingestProgress.status === 'running' || 
              ingestProgress.status === 'scanning' || 
              ingestProgress.status === 'processing') ? (
          <div className="ingest-in-progress">
            <h3>Video Processing in Progress</h3>
            {error && <div className="error-message">{error}</div>}
          </div>
        ) : (
          // Show ingest form when not ingesting
          <>
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
                <button onClick={() => toggleOption('force_reprocess')} className="checkbox">
                  {ingestOptions.force_reprocess ? <FiCheckSquare /> : <FiSquare />}
                </button>
                <div className="option-content">
                  <span className="option-label">Re-ingest existing files</span>
                  <span className="option-desc">Process files even if they've been ingested before</span>
                </div>
              </label>
            </div>

            <button 
              onClick={startIngest} 
              className="start-ingest-btn"
              disabled={!selectedDirectory}
            >
              <FiPlay /> Start Ingest
            </button>
            {error && <div className="error-message">{error}</div>}
          </>
        )}

        {ingestProgress && showProgress && (
          <div className="ingest-progress-container">
            <h3>Ingest Progress</h3>
            <div className="progress-bar-container">
              <div className="progress-bar-background">
                <div 
                  className={`progress-bar-fill ${ingestProgress?.status === 'failed' ? 'failed' : ''}`}
                  style={{ width: `${ingestProgress?.progress || 0}%` }}
                />
              </div>
              <span className="progress-percentage">{ingestProgress?.progress || 0}%</span>
            </div>
            <p><strong>Status:</strong> {ingestProgress?.status}</p>
            <p><strong>Message:</strong> {ingestProgress?.message || 'No message'}</p>
            
            {ingestProgress?.current_file && (
              <div className="current-file">
                <p><strong>Current file:</strong> {ingestProgress.current_file}</p>
              </div>
            )}
            
            {ingestProgress?.processed_files && ingestProgress.processed_files.length > 0 && (
              <div className="processed-files">
                <h4>Processed Files ({ingestProgress.processed_files.length})</h4>
                <div className="file-list">
                  <div className="file-list-inner">
                    {ingestProgress.processed_files.slice(-10).map((file, index) => (
                      <div key={index} className="file-item">
                        <span className="file-name">{file.file_name || file.path || 'Unknown file'}</span>
                        <div className="file-status-container">
                          <span className={`file-status ${file.status}`}>{file.status}</span>
                          {file.status === 'processing' && file.current_step && (
                            <span className="file-step">{file.current_step}</span>
                          )}
                          
                          {/* Individual file progress bar */}
                          {file.progress_percentage !== undefined && (
                            <div className="file-progress">
                              <div className="file-progress-bar-background">
                                <div 
                                  className={`file-progress-bar-fill ${file.status === 'failed' ? 'failed' : ''}`}
                                  style={{ width: `${file.progress_percentage}%` }}
                                />
                              </div>
                              <span className="file-progress-percentage">{file.progress_percentage}%</span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  {ingestProgress.processed_files.length > 10 && (
                    <div className="more-files">
                      ...and {ingestProgress.processed_files.length - 10} more files
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <div className="progress-stats">
              {ingestProgress?.processed_count !== undefined && (
                <div className="stat-item">
                  <strong>Processed:</strong> {ingestProgress.processed_count} files
                </div>
              )}
              {ingestProgress?.failed_count !== undefined && (
                <div className="stat-item">
                  <strong>Failed:</strong> {ingestProgress.failed_count} files
                </div>
              )}
              {ingestProgress?.total_count !== undefined && (
                <div className="stat-item">
                  <strong>Total:</strong> {ingestProgress.total_count} files
                </div>
              )}
            </div>
            
            {ingestProgress?.status === 'failed' && (
              <button onClick={() => setShowProgress(false)} className="dismiss-btn">
                Dismiss
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default IngestPanel;
