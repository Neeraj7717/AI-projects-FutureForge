import React, { useState } from 'react';
import { Box, styled } from '@mui/material';
import Sidebar from './Sidebar';
import Preview from './Preview';
import { mockPosts } from '../data/mockData';

const Container = styled(Box)({
  display: 'flex',
  height: '100vh',
  backgroundColor: '#FAFAFA',
});

const SidebarContainer = styled(Box)({
  width: '400px',
  height: '80vh', // Full viewport height
  maxHeight: '100vh', // Maximum height limit
  backgroundColor: '#FFFFFF',
  borderRight: '3px solid #DBDBDB',
  overflowY: 'auto',
  flexShrink: 0,
  boxShadow: '2px 0 10px rgba(0, 0, 0, 0.1)',
  position: 'relative',
  '&::after': {
    content: '""',
    position: 'absolute',
    right: '-3px',
    top: 50,
    bottom: 0,
    width: '4px',
    background: 'linear-gradient(180deg, #0095F6 0%, #B32EFF 100%)',
    borderRadius: '2px',
  },
});

const PreviewContainer = styled(Box)({
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '300px',
  backgroundColor: '#F8F9FA',
  backgroundImage: 'radial-gradient(circle at 25% 25%, rgba(0, 149, 246, 0.05) 0%, transparent 50%), radial-gradient(circle at 75% 75%, rgba(179, 46, 255, 0.05) 0%, transparent 50%)',
  minHeight: '100vh',
});

interface WorkflowData {
  step: number;
  selectedPost: any;
  keyword: string;
  dmMessage: string;
}

const InstagramWorkflowBuilder: React.FC = () => {
  const [workflowData, setWorkflowData] = useState<WorkflowData>({
    step: 1,
    selectedPost: null,
    keyword: '',
    dmMessage: '',
  });

  const handleNext = () => {
    if (workflowData.step < 3) {
      setWorkflowData(prev => ({ ...prev, step: prev.step + 1 }));
    }
  };

  const handleBack = () => {
    if (workflowData.step > 1) {
      setWorkflowData(prev => ({ ...prev, step: prev.step - 1 }));
    }
  };

  const handlePostSelect = (post: any) => {
    setWorkflowData(prev => ({ ...prev, selectedPost: post }));
  };

  const handleKeywordChange = (keyword: string) => {
    setWorkflowData(prev => ({ ...prev, keyword }));
  };

  const handleDMMessageChange = (message: string) => {
    setWorkflowData(prev => ({ ...prev, dmMessage: message }));
  };

  const handleGoLive = () => {
    console.log('Going live with workflow:', workflowData);
    // Handle go live functionality
  };

  const canProceed = () => {
    switch (workflowData.step) {
      case 1:
        return workflowData.selectedPost !== null;
      case 2:
        return workflowData.keyword.trim().length > 0;
      case 3:
        return workflowData.dmMessage.trim().length > 0;
      default:
        return false;
    }
  };

  return (
    <Container>
      <SidebarContainer>
        <Sidebar
          step={workflowData.step}
          selectedPost={workflowData.selectedPost}
          keyword={workflowData.keyword}
          dmMessage={workflowData.dmMessage}
          posts={mockPosts}
          onPostSelect={handlePostSelect}
          onKeywordChange={handleKeywordChange}
          onDMMessageChange={handleDMMessageChange}
          onNext={handleNext}
          onBack={handleBack}
          canProceed={canProceed()}
        />
      </SidebarContainer>
      
      <PreviewContainer>
        <Preview
          step={workflowData.step}
          selectedPost={workflowData.selectedPost}
          keyword={workflowData.keyword}
          dmMessage={workflowData.dmMessage}
          onGoLive={handleGoLive}
        />
      </PreviewContainer>
    </Container>
  );
};

export default InstagramWorkflowBuilder; 