import React from 'react';
import { Box, styled, IconButton } from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';

const HeaderContainer = styled(Box)({
  height: '44px',
  backgroundColor: '#FAFAFA',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '0 16px',
  borderBottom: '1px solid #DBDBDB',
  position: 'relative',
  zIndex: 10,
});

const BackButton = styled(IconButton)({
  width: '44px',
  height: '44px',
  color: '#262626',
  padding: 0,
  '&:hover': {
    backgroundColor: 'transparent',
  },
});

const Title = styled(Box)({
  fontSize: '18px',
  fontWeight: 600,
  color: '#262626',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
  position: 'absolute',
  left: '50%',
  top: '50%',
  transform: 'translate(-50%, -50%)',
});

const Spacer = styled(Box)({
  width: '44px',
});

interface InstagramHeaderProps {
  title: string;
  onBack?: () => void;
}

const InstagramHeader: React.FC<InstagramHeaderProps> = ({ title, onBack }) => {
  return (
    <HeaderContainer>
      <BackButton onClick={onBack}>
        <ChevronLeftIcon sx={{ fontSize: 24 }} />
      </BackButton>
      <Title>{title}</Title>
      <Spacer />
    </HeaderContainer>
  );
};

export default InstagramHeader; 