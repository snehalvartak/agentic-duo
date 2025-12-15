import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, X } from 'lucide-react';

export interface ToastProps {
    message: string;
    type: 'success' | 'error' | 'info';
    onClose: () => void;
    duration?: number;
}

export const Toast: React.FC<ToastProps> = ({ message, type, onClose, duration = 3000 }) => {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    const variants = {
        initial: { opacity: 0, y: -50, scale: 0.9 },
        animate: { opacity: 1, y: 0, scale: 1 },
        exit: { opacity: 0, y: -20, scale: 0.9 },
    };

    const colors = {
        success: 'bg-green-500/10 border-green-500/20 text-green-400',
        error: 'bg-red-500/10 border-red-500/20 text-red-400',
        info: 'bg-blue-500/10 border-blue-500/20 text-blue-400',
    };

    const icons = {
        success: <CheckCircle className="w-5 h-5 text-green-400" />,
        error: <XCircle className="w-5 h-5 text-red-400" />,
        info: <div className="w-5 h-5 rounded-full border-2 border-current" />,
    };

    // Using inline styles for simplicity if tailwind isn't fully configured
    // But based on "premium design" request, we'll try to use a nice glassmorphism style

    return (
        <motion.div
            layout
            initial="initial"
            animate="animate"
            exit="exit"
            variants={variants}
            className="fixed top-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-6 py-4 rounded-xl shadow-2xl backdrop-blur-md border"
            style={{
                backgroundColor: type === 'success' ? 'rgba(20, 83, 45, 0.9)' : type === 'error' ? 'rgba(127, 29, 29, 0.9)' : 'rgba(30, 41, 59, 0.9)',
                borderColor: type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6',
                color: 'white',
                minWidth: '300px',
                maxWidth: '90vw',
            }}
        >
            <div className="shrink-0">
                {icons[type]}
            </div>

            <p className="flex-1 font-medium text-sm">{message}</p>

            <button
                onClick={onClose}
                className="shrink-0 p-1 hover:bg-white/10 rounded-full transition-colors"
            >
                <X size={16} />
            </button>
        </motion.div>
    );
};
