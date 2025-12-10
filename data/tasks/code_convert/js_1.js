// JavaScript version of python_1.py

function main() {
    const readline = require('readline');
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    rl.question('', (line) => {
        line = line.trim();
        if (!line) {
            // 没有输入直接退出
            rl.close();
            return;
        }

        try {
            const [a, b] = line.split(' ').map(Number);
            if (isNaN(a) || isNaN(b)) {
                throw new Error('Invalid input');
            }
            
            console.log(Math.floor(a / b));
            console.log(a % b);
        } catch (error) {
            console.error("Input must be two integers");
            process.exit(1);
        }
        
        rl.close();
    });
}

// 直接调用main函数
main();
