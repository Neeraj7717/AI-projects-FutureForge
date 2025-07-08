import React from 'react';
import { Box, styled } from '@mui/material';

const Container = styled(Box)({
  padding: '20px 16px',
  backgroundColor: '#FFFFFF',
  borderBottom: '1px solid #DBDBDB',
});

const H1 = styled(Box)({
  fontSize: '24px',
  fontWeight: 600,
  color: '#262626',
  marginBottom: '20px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const H2 = styled(Box)({
  fontSize: '20px',
  fontWeight: 600,
  color: '#262626',
  marginBottom: '16px',
  fontFamily: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
});

const InstagramDivider = styled(Box)({
  height: '1px',
  backgroundColor: '#DBDBDB',
  margin: '20px 0',
});

interface StepContainerProps {
  children: React.ReactNode;
}

const StepContainer: React.FC<StepContainerProps> = ({ children }) => {
  return <Container>{children}</Container>;
};

export { H1, H2, InstagramDivider };
export default StepContainer; 