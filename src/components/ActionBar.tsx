import React from 'react';
import { Box, styled, Button } from '@mui/material';

const ActionBarContainer = styled(Box)({
  backgroundColor: '#FFFFFF',
  borderTop: '1px solid #DBDBDB',
  padding: '16px',
  display: 'flex',
  gap: '12px',
  alignItems: 'center',
  justifyContent: 'space-between',
  position: 'relative',
  zIndex: 10,
});

const SecondaryButton = styled(Button)({
  color: '#262626',
  fontSize: '16px',
  fontWeight: 600,
  textTransform: 'none',
  padding: '12px 24px',
  border: '1px solid #DBDBDB',
  borderRadius: '8px',
  backgroundColor: '#FFFFFF',
  '&:hover': {
    backgroundColor: '#F8F9FA',
    borderColor: '#262626',
  },
});

const PrimaryButton = styled(Button)({
  background: 'linear-gradient(45deg, #4CB5F9, #B32EFF)',
  color: '#FFFFFF',
  fontSize: '16px',
  fontWeight: 600,
  textTransform: 'none',
  padding: '12px 24px',
  borderRadius: '8px',
  border: 'none',
  '&:hover': {
    background: 'linear-gradient(45deg, #3AA4E8, #A21EE6)',
  },
  '&:disabled': {
    background: '#DBDBDB',
    color: '#8E8E8E',
  },
});

const LiveButton = styled(Button)({
  background: 'linear-gradient(45deg, #FF6B6B, #FF8E53)',
  color: '#FFFFFF',
  fontSize: '16px',
  fontWeight: 600,
  textTransform: 'none',
  padding: '12px 24px',
  borderRadius: '8px',
  border: 'none',
  '&:hover': {
    background: 'linear-gradient(45deg, #FF5252, #FF7043)',
  },
});

interface ActionBarProps {
  step: number;
  onBack: () => void;
  onNext: () => void;
  onGoLive: () => void;
  canProceed: boolean;
}

const ActionBar: React.FC<ActionBarProps> = ({
  step,
  onBack,
  onNext,
  onGoLive,
  canProceed,
}) => {
  return (
    <ActionBarContainer>
      {step > 1 && (
        <SecondaryButton onClick={onBack}>
          Back
        </SecondaryButton>
      )}
      
      {step < 3 && (
        <PrimaryButton
          onClick={onNext}
          disabled={!canProceed}
          sx={{ marginLeft: step === 1 ? 'auto' : '0' }}
        >
          Next
        </PrimaryButton>
      )}
      
      {step === 3 && (
        <LiveButton onClick={onGoLive}>
          Go Live
        </LiveButton>
      )}
    </ActionBarContainer>
  );
};

export default ActionBar; 