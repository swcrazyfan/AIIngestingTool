import React, { useState, useEffect } from 'react';
import { pipelineApi } from '../api/client';
import { PipelineStep } from '../types/api';
import AccordionItem from './AccordionItem';
import { FiSettings, FiSave, FiCheckSquare, FiSquare } from 'react-icons/fi';

const SettingsPanel: React.FC = () => {
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<string>('standard');
  const [customSteps, setCustomSteps] = useState<{[key: string]: boolean}>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPipelineSteps();
  }, []);

  const loadPipelineSteps = async () => {
    try {
      const stepsData = await pipelineApi.getSteps();
      setSteps(stepsData);
      
      // Initialize custom steps with default values
      const initialSteps: {[key: string]: boolean} = {};
      stepsData.forEach(step => {
        initialSteps[step.id] = step.enabled_by_default || false;
      });
      setCustomSteps(initialSteps);
    } catch (error) {
      console.error('Failed to load pipeline steps:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleStep = (stepId: string) => {
    setCustomSteps(prev => ({
      ...prev,
      [stepId]: !prev[stepId]
    }));
    setSelectedProfile('custom');
  };

  const applyProfile = (profileName: string) => {
    setSelectedProfile(profileName);
    
    const profiles = {
      fast: {
        checksum_generation: true,
        mediainfo_extraction: true,
        thumbnail_generation: true,
        ai_analysis: false,
        generate_embeddings: false
      },
      standard: {
        checksum_generation: true,
        mediainfo_extraction: true,
        ffprobe_extraction: true,
        thumbnail_generation: true,
        ai_analysis: true,
        generate_embeddings: false
      },
      comprehensive: {
        checksum_generation: true,
        mediainfo_extraction: true,
        ffprobe_extraction: true,
        exiftool_extraction: true,
        thumbnail_generation: true,
        ai_analysis: true,
        generate_embeddings: true,
        transcript_generation: true
      }
    };

    if (profiles[profileName as keyof typeof profiles]) {
      setCustomSteps(profiles[profileName as keyof typeof profiles]);
    }
  };

  if (loading) {
    return (
      <div className="video-library">
        <div className="loading-state">
          <div className="spinner" />
          <h3>Loading Settings</h3>
          <p>Getting pipeline configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-library">
      <div className="library-header">
        <h3>Processing Settings</h3>
        <div className="library-controls">
          <button className="refresh-button">
            <FiSave />
          </button>
        </div>
      </div>

      {/* Processing Profiles */}
      <AccordionItem title="Processing Profiles" startOpen={true}>
        <div className="filter-controls">
          <div className="filter-group">
            <label>Profile:</label>
            <select value={selectedProfile} onChange={(e) => applyProfile(e.target.value)}>
              <option value="fast">Fast - Quick processing</option>
              <option value="standard">Standard - Balanced processing</option>
              <option value="comprehensive">Comprehensive - Full analysis</option>
              <option value="custom">Custom - Manual configuration</option>
            </select>
          </div>
        </div>
      </AccordionItem>

      {/* Processing Steps */}
      <AccordionItem title="Processing Steps" startOpen={true}>
        <div className="video-grid video-grid-small">
          {steps.map((step) => (
            <div key={step.id} className="stat-overview-card">
              <div className="video-info">
                <div className="video-title">
                  <button
                    className="checkbox"
                    onClick={() => toggleStep(step.id)}
                    style={{ color: customSteps[step.id] ? '#16a34a' : '#666' }}
                  >
                    {customSteps[step.id] ? <FiCheckSquare /> : <FiSquare />}
                  </button>
                  {step.name}
                </div>
                <div className="video-summary">
                  {step.description || `Process ${step.name.toLowerCase()}`}
                </div>
              </div>
            </div>
          ))}
        </div>
      </AccordionItem>

      {/* Save Configuration */}
      <div className="library-header">
        <button className="apply-filters-button">
          <FiSave />
          Save Configuration
        </button>
      </div>
    </div>
  );
};

export default SettingsPanel;
