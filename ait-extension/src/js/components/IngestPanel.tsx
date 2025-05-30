import React, { useState, useEffect } from 'react';
import { ingestApi } from '../api/client';
import { IngestProgress } from '../types/api';
import { evalTS, evalES } from '../lib/utils/bolt';
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
    force_reprocess: true // Changed from false to true to default reingest on
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showProgress, setShowProgress] = useState<boolean>(false);
  
  // Use the global WebSocket connection
  const { ingestProgress, connected, setIngestProgress } = useWebSocket();
// State to control visibility of the progress log area
  const [showLog, setShowLog] = useState<boolean>(false);

  const selectDirectory = async () => {
    try {
      // Clear any previous error messages before attempting selection
      setError(null);
      const directory = await evalTS("selectDirectory");
      if (directory && typeof directory === 'string') { // Ensure it's a string before setting
        setSelectedDirectory(directory);
      } else if (directory) { // It returned something, but not a string
        console.warn("selectDirectory returned a non-string value:", directory);
        setError("Failed to get a valid directory path."); // User-friendly error
      }
      // If directory is null (e.g. user cancelled dialog), do nothing, no error needed.
    } catch (error: any) {
      console.error('Failed to select directory:', error);
      // Provide a user-friendly error message
      const errorMessage = error && error.message ? error.message : "An unknown error occurred.";
      setError(`Failed to select directory: ${errorMessage}`);
    }
  };

  const startIngest = async () => {
    if (!selectedDirectory) return;
    
    setIsLoading(true);
    // Clear previous errors before new attempt
    setError(null); 
    try {
      await ingestApi.startIngest(selectedDirectory, ingestOptions);
      
      // Show progress section and clear any errors
      setShowProgress(true);
setShowLog(true); // Also show the log area
      setError(null); // Ensure error is cleared on successful start
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
          
          // Clear errors if we successfully got progress data
          if (progressData) {
            setError(null);
          }
          
          // If there's an active ingest process
          if (progressData && (progressData.status === 'running' || 
                              progressData.status === 'scanning' || 
                              progressData.status === 'processing')) {
            setShowProgress(true);
setShowLog(true); // Show log if process is ongoing
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
      // Clear any connection errors when we receive valid progress data
      setError(null);
      
      // Show progress section if there's an active process
      const activeStatuses = ['starting', 'running', 'scanning', 'processing'];
      // const completeStatuses = ['idle', 'completed', 'failed']; // No longer needed for auto-hide
      
      if (activeStatuses.includes(ingestProgress.status)) {
        setShowProgress(true);
setShowLog(true); // Keep log visible if active
      }
      
      // // // Hide progress after a delay when process completes
      // //      if (completeStatuses.includes(ingestProgress.status)) {
        // //        setTimeout(() => {
          // //          setShowProgress(false);
        // //        }, 5000);  // Show completed status for 5 seconds
      // //      }
// Ensure log stays visible if there's content, even if process completes
      if (ingestProgress && ((ingestProgress.processed_files && ingestProgress.processed_files.length > 0) || ingestProgress.message || ingestProgress.status)) {
        setShowLog(true);
      }
    }
  }, [ingestProgress]);

  // Poll for progress updates when WebSocket is not connected
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    
    if (!connected && (showProgress || showLog)) { // Poll if either progress or log is shown
      // Poll every 2 seconds when WebSocket is not available
      intervalId = setInterval(async () => {
        try {
          const progress = await ingestApi.getProgress();
          // If we got progress data, update UI and clear any connection errors
          if (progress) {
            setIngestProgress(progress);
            setError(null); // Clear connection errors when API is responsive
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
  }, [connected, showProgress, showLog]);
const clearLog = () => {
    setIngestProgress({
      status: 'idle',
      progress: 0,
      message: '',
      processed_files: [],
      current_file: undefined,
      error: undefined,
      processed_count: 0,
      results_count: 0,
      failed_count: 0,
      total_count: 0
    });
    setShowProgress(false);  // Hide the main progress bar section
    setShowLog(false);       // Hide the log area
    setError(null);          // Clear any general errors
  };

  const formatETR = (seconds: number | undefined): string => {
    if (seconds === undefined || seconds === null || seconds < 0) {
      return '--';
    }
    if (seconds === 0) {
      return 'Done';
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    if (minutes > 0) {
      return `${minutes}m ${remainingSeconds}s rem.`;
    }
    return `${remainingSeconds}s rem.`;
  };

  return (
    <div className="ingest-panel">
      <h2>Video Ingest</h2>
      
      <div className="ingest-panel-content scrollable-content">
        {isLoading && !showProgress && !showLog ? (
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
              ingestApi.getProgress().then((progressData) => {
                setIngestProgress(progressData); // Update progress on retry
                setIsLoading(false);
              }).catch(() => {
                setIsLoading(false);
                setError('Failed to connect to server');
              });
            }}>Retry</button>
          </div>
        ) : ingestProgress && (ingestProgress.status === 'running' ||
              ingestProgress.status === 'scanning' ||
              ingestProgress.status === 'processing') && !showLog ? ( // Only show this if log isn't visible yet
          <div className="ingest-in-progress">
            <h3>Video Processing in Progress</h3>
            {error && <div className="error-message">{error}</div>}
          </div>
        ) : (
          // Show ingest form when not ingesting or log is not primary focus
          (!ingestProgress || !showLog || !['running', 'scanning', 'processing'].includes(ingestProgress.status)) && (
          <>
            <div className="directory-selection">
              <div className="directory-input-group">
                <input
                  type="text"
                  className="selected-path-input"
                  value={selectedDirectory}
                  onChange={(e) => setSelectedDirectory(e.target.value)}
                  placeholder="Enter or select directory path..."
                />
                <button onClick={selectDirectory} className="select-directory-btn">
                  <FiFolder /> Select
                </button>
              </div>
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
              disabled={!selectedDirectory || (!!ingestProgress && ['running', 'scanning', 'processing'].includes(ingestProgress.status))}
            >
              <FiPlay /> Start Ingest
            </button>
            {error && (!ingestProgress || !showLog) && <div className="error-message">{error}</div>}
          </>
          )
        )}

        {/* Ingest Status Section (Overall Progress) */}
        {ingestProgress && showProgress && (
          <div className="ingest-progress-container">
            <h3>Ingest Status</h3>
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
            {/* Removed old dismiss button */}
          </div>
        )}

        {/* Persistent Log Section */}
        {ingestProgress && showLog && (
          <div className="ingest-log-container">
            <div className="log-header">
              <h3>Ingest Log</h3>
              <button onClick={clearLog} className="clear-log-btn">
                Clear Log
              </button>
            </div>
            
            {ingestProgress?.processed_files && ingestProgress.processed_files.length > 0 ? (
              <div className="processed-files-log">
                <div className="file-list-inner scrollable-log"> {/* Ensure .scrollable-log is styled for scrolling */}
                  {ingestProgress.processed_files.map((file, index) => (
                    <div key={index} className="file-item">
                      <span className="file-name">{file.file_name || file.path || 'Unknown file'}</span>
                      <div className="file-status-container">
                        <span className={`file-status ${file.status}`}>
                          {file.status === 'skipped'
                            ? 'Already in library'
                            : file.status === 'failed'
                              ? 'Failed'
                              : file.status === 'completed'
                                ? 'Completed'
                                : file.status.charAt(0).toUpperCase() + file.status.slice(1)}
                        </span>
                        {file.status === 'failed' && file.error && (
                          <span className="file-error" title={file.error}>{file.error}</span>
                        )}
                        {file.status === 'skipped' && file.error && (
                          <span className="file-skipped-reason" title={file.error}>{file.error}</span>
                        )}
                        {file.status === 'processing' && file.current_step && (
                          <span className="file-step">{file.current_step}</span>
                        )}
                        
                        {/* Display compression details if available and step is video_compression */}
                        {file.status === 'processing' && file.current_step === 'video_compression' && (
                          <div className="compression-details">
                            {file.compression_current_rate !== undefined && (
                              <span className="compression-rate">Rate: {file.compression_current_rate.toFixed(2)} FPS</span>
                            )}
                            {file.compression_speed && (
                              <span className="compression-speed">Speed: {file.compression_speed}</span>
                            )}
                            {file.compression_etr_seconds !== undefined && (
                              <span className="compression-etr">ETR: {formatETR(file.compression_etr_seconds)}</span>
                            )}
                            {file.compression_processed_frames !== undefined && file.compression_total_frames !== undefined && (
                                <span className="compression-frames">
                                    Frames: {file.compression_processed_frames} / {file.compression_total_frames}
                                </span>
                            )}
                          </div>
                        )}
                        {file.compression_error_detail && (
                            <span className="file-error" title={file.compression_error_detail}>Compression Error: {file.compression_error_detail}</span>
                        )}

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
              </div>
            ) : (
              <p className="empty-log-message">Log is empty. Start an ingest to see progress.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default IngestPanel;
