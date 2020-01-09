
section reset

global main_main
global bsp_exit

global start
start:
    call main_main
    call bsp_exit

global bsp_syscall
bsp_syscall:
    mov rax, rdi ; abi param 1
    mov rdi, rsi ; abi param 2
    mov rsi, rdx ; abi param 3
    mov rdx, rcx ; abi param 4
    syscall
    ret

