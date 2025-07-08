import React from 'react';
import { Box, styled } from '@mui/material';

const StatusBarContainer = styled(Box)({
  height: '44px',
  backgroundColor: '#FAFAFA',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 20px',
  fontSize: '14px',
  fontWeight: 600,
  color: '#000',
  position: 'relative',
  zIndex: 10,
});

const Time = styled(Box)({
  fontSize: '15px',
  fontWeight: 600,
});

const RightIcons = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
});

const SignalIcon = styled(Box)({
  width: '18px',
  height: '12px',
  position: 'relative',
  '&::before': {
    content: '""',
    position: 'absolute',
    left: '0',
    bottom: '0',
    width: '3px',
    height: '6px',
    backgroundColor: '#000',
    borderRadius: '1px 1px 0 0',
  },
  '&::after': {
    content: '""',
    position: 'absolute',
    left: '4px',
    bottom: '0',
    width: '3px',
    height: '9px',
    backgroundColor: '#000',
    borderRadius: '1px 1px 0 0',
  },
});

const WifiIcon = styled(Box)({
  width: '16px',
  height: '12px',
  position: 'relative',
  '&::before': {
    content: '""',
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: '12px',
    height: '8px',
    border: '2px solid #000',
    borderTop: 'none',
    borderRadius: '0 0 6px 6px',
  },
});

const BatteryIcon = styled(Box)({
  width: '25px',
  height: '12px',
  border: '1px solid #000',
  borderRadius: '2px',
  position: 'relative',
  '&::before': {
    content: '""',
    position: 'absolute',
    right: '-3px',
    top: '50%',
    transform: 'translateY(-50%)',
    width: '2px',
    height: '4px',
    backgroundColor: '#000',
    borderRadius: '0 1px 1px 0',
  },
  '&::after': {
    content: '""',
    position: 'absolute',
    left: '2px',
    top: '2px',
    width: '19px',
    height: '6px',
    backgroundColor: '#000',
    borderRadius: '1px',
  },
});

const IOSStatusBar: React.FC = () => {
  const getCurrentTime = () => {
    const now = new Date();
    return now.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  return (
    <StatusBarContainer>
      <Time>{getCurrentTime()}</Time>
      <RightIcons>
        <SignalIcon />
        <WifiIcon />
        <BatteryIcon />
      </RightIcons>
    </StatusBarContainer>
  );
};

export default IOSStatusBar; 